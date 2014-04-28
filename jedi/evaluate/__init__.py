"""
Evaluation of Python code in |jedi| is based on three assumptions:

* Code is recursive (to weaken this assumption, the
  :mod:`jedi.evaluate.dynamic` module exists).
* No magic is being used:

  - metaclasses
  - ``setattr()`` / ``__import__()``
  - writing to ``globals()``, ``locals()``, ``object.__dict__``
* The programmer is not a total dick, e.g. like `this
  <https://github.com/davidhalter/jedi/issues/24>`_ :-)

That said, there's mainly one entry point in this script: ``eval_statement``.
This is where autocompletion starts. Everything you want to complete is either
a ``Statement`` or some special name like ``class``, which is easy to complete.

Therefore you need to understand what follows after ``eval_statement``. Let's
make an example::

    import datetime
    datetime.date.toda# <-- cursor here

First of all, this module doesn't care about completion. It really just cares
about ``datetime.date``. At the end of the procedure ``eval_statement`` will
return the ``datetime`` class.

To *visualize* this (simplified):

- ``eval_statement`` - ``<Statement: datetime.date>``

    - Unpacking of the statement into ``[[<Call: datetime.date>]]``
- ``eval_expression_list``, calls ``eval_call`` with ``<Call: datetime.date>``
- ``eval_call`` - searches the ``datetime`` name within the module.

This is exactly where it starts to get complicated. Now recursions start to
kick in. The statement has not been resolved fully, but now we need to resolve
the datetime import. So it continues

- follow import, which happens in the :mod:`jedi.evaluate.imports` module.
- now the same ``eval_call`` as above calls ``follow_path`` to follow the
  second part of the statement ``date``.
- After ``follow_path`` returns with the desired ``datetime.date`` class, the
  result is being returned and the recursion finishes.

Now what would happen if we wanted ``datetime.date.foo.bar``? Just two more
calls to ``follow_path`` (which calls itself with a recursion). What if the
import would contain another Statement like this::

    from foo import bar
    Date = bar.baz

Well... You get it. Just another ``eval_statement`` recursion. It's really
easy. Just that Python is not that easy sometimes. To understand tuple
assignments and different class scopes, a lot more code had to be written.  Yet
we're still not talking about Descriptors and Nested List Comprehensions, just
the simple stuff.

So if you want to change something, write a test and then just change what you
want. This module has been tested by about 600 tests. Don't be afraid to break
something. The tests are good enough.

I need to mention now that this recursive approach is really good because it
only *evaluates* what needs to be *evaluated*. All the statements and modules
that are not used are just being ignored. It's a little bit similar to the
backtracking algorithm.


.. todo:: nonlocal statement, needed or can be ignored? (py3k)
"""
import itertools

from jedi._compatibility import next, hasattr, unicode
from jedi.parser import representation as pr
from jedi.parser.tokenize import Token
from jedi import debug
from jedi.evaluate import representation as er
from jedi.evaluate import imports
from jedi.evaluate import recursion
from jedi.evaluate import iterable
from jedi.evaluate.cache import memoize_default
from jedi.evaluate import stdlib
from jedi.evaluate import finder
from jedi.evaluate import compiled
from jedi.evaluate import precedence


class Evaluator(object):
    def __init__(self):
        self.memoize_cache = {}  # for memoize decorators
        self.import_cache = {}  # like `sys.modules`.
        self.compiled_cache = {}  # see `compiled.create()`
        self.recursion_detector = recursion.RecursionDetector()
        self.execution_recursion_detector = recursion.ExecutionRecursionDetector()

    def find_types(self, scope, name_str, position=None, search_global=False,
                   is_goto=False, resolve_decorator=True):
        """
        This is the search function. The most important part to debug.
        `remove_statements` and `filter_statements` really are the core part of
        this completion.

        :param position: Position of the last statement -> tuple of line, column
        :return: List of Names. Their parents are the types.
        """
        f = finder.NameFinder(self, scope, name_str, position)
        scopes = f.scopes(search_global)
        if is_goto:
            return f.filter_name(scopes)
        return f.find(scopes, resolve_decorator)

    @memoize_default(default=[], evaluator_is_first_arg=True)
    @recursion.recursion_decorator
    @debug.increase_indent
    def eval_statement(self, stmt, seek_name=None):
        """
        The starting point of the completion. A statement always owns a call
        list, which are the calls, that a statement does. In case multiple
        names are defined in the statement, `seek_name` returns the result for
        this name.

        :param stmt: A `pr.Statement`.
        """
        debug.dbg('eval_statement %s (%s)', stmt, seek_name)
        expression_list = stmt.expression_list()

        result = self.eval_expression_list(expression_list)

        ass_details = stmt.assignment_details
        if ass_details and ass_details[0][1] != '=' and not isinstance(stmt, er.InstanceElement):  # TODO don't check for this.
            expr_list, operator = ass_details[0]
            # `=` is always the last character in aug assignments -> -1
            operator = operator[:-1]
            name = str(expr_list[0].name)
            left = self.find_types(stmt.parent, name, stmt.start_pos)
            if isinstance(stmt.parent, pr.ForFlow):
                # iterate through result and add the values, that's possible
                # only in for loops without clutter, because they are
                # predictable.
                for r in result:
                    left = precedence.calculate(self, left, operator, [r])
                result = left
            else:
                result = precedence.calculate(self, left, operator, result)
        elif len(stmt.get_defined_names()) > 1 and seek_name and ass_details:
            # Assignment checking is only important if the statement defines
            # multiple variables.
            new_result = []
            for ass_expression_list, op in ass_details:
                new_result += finder.find_assignments(ass_expression_list[0], result, seek_name)
            result = new_result
        return result

    def eval_expression_list(self, expression_list):
        """
        `expression_list` can be either `pr.Array` or `list of list`.
        It is used to evaluate a two dimensional object, that has calls, arrays and
        operators in it.
        """
        debug.dbg('eval_expression_list: %s', expression_list)
        p = precedence.create_precedence(expression_list)
        return self.process_precedence_element(p) or []

    def process_precedence_element(self, el):
        if el is None:
            return None
        else:
            if isinstance(el, precedence.Precedence):
                return self._eval_precedence(el)
            else:
                # normal element, no operators
                return self._eval_statement_element(el)

    def _eval_precedence(self, _precedence):
        left = self.process_precedence_element(_precedence.left)
        right = self.process_precedence_element(_precedence.right)
        return precedence.calculate(self, left, _precedence.operator, right)

    def _eval_statement_element(self, element):
        if pr.Array.is_type(element, pr.Array.NOARRAY):
            r = list(itertools.chain.from_iterable(self.eval_statement(s)
                                                   for s in element))
            call_path = element.generate_call_path()
            next(call_path, None)  # the first one has been used already
            return self.follow_path(call_path, r, element.parent)
        elif isinstance(element, pr.ListComprehension):
            loop = _evaluate_list_comprehension(element)
            # Caveat: parents are being changed, but this doesn't matter,
            # because nothing else uses it.
            element.stmt.parent = loop
            return self.eval_statement(element.stmt)
        elif isinstance(element, pr.Lambda):
            return [er.Function(self, element)]
        # With things like params, these can also be functions...
        elif isinstance(element, pr.Base) and element.isinstance(
                er.Function, er.Class, er.Instance, iterable.ArrayInstance):
            return [element]
        # The string tokens are just operations (+, -, etc.)
        elif isinstance(element, compiled.CompiledObject):
            return [element]
        elif not isinstance(element, Token):
            return self.eval_call(element)
        else:
            return []

    def eval_call(self, call):
        """Follow a call is following a function, variable, string, etc."""
        path = call.generate_call_path()

        # find the statement of the Scope
        s = call
        while not s.parent.isinstance(pr.IsScope):
            s = s.parent
        return self.eval_call_path(path, s.parent, s.start_pos)

    def eval_call_path(self, path, scope, position):
        """
        Follows a path generated by `pr.StatementElement.generate_call_path()`.
        """
        current = next(path)

        if isinstance(current, pr.Array):
            types = [iterable.Array(self, current)]
        else:
            if isinstance(current, pr.NamePart):
                # This is the first global lookup.
                types = self.find_types(scope, current, position=position,
                                        search_global=True)
            else:
                # for pr.Literal
                types = [compiled.create(self, current.value)]
            types = imports.strip_imports(self, types)

        return self.follow_path(path, types, scope)

    def follow_path(self, path, types, call_scope):
        """
        Follows a path like::

            self.follow_path(iter(['Foo', 'bar']), [a_type], from_somewhere)

        to follow a call like ``module.a_type.Foo.bar`` (in ``from_somewhere``).
        """
        results_new = []
        iter_paths = itertools.tee(path, len(types))

        for i, typ in enumerate(types):
            fp = self._follow_path(iter_paths[i], typ, call_scope)
            if fp is not None:
                results_new += fp
            else:
                # This means stop iteration.
                return types
        return results_new

    def _follow_path(self, path, typ, scope):
        """
        Uses a generator and tries to complete the path, e.g.::

            foo.bar.baz

        `_follow_path` is only responsible for completing `.bar.baz`, the rest
        is done in the `follow_call` function.
        """
        # current is either an Array or a Scope.
        try:
            current = next(path)
        except StopIteration:
            return None
        debug.dbg('_follow_path: %s in scope %s', current, typ)

        result = []
        if isinstance(current, pr.Array):
            # This must be an execution, either () or [].
            if current.type == pr.Array.LIST:
                if hasattr(typ, 'get_index_types'):
                    slc = iterable.create_indexes_or_slices(self, current)
                    result = typ.get_index_types(slc)
            elif current.type not in [pr.Array.DICT]:
                # Scope must be a class or func - make an instance or execution.
                result = self.execute(typ, current)
            else:
                # Curly braces are not allowed, because they make no sense.
                debug.warning('strange function call with {} %s %s', current, typ)
        else:
            # The function must not be decorated with something else.
            if typ.isinstance(er.Function):
                typ = typ.get_magic_function_scope()
            else:
                # This is the typical lookup while chaining things.
                if filter_private_variable(typ, scope, current):
                    return []
            types = self.find_types(typ, current)
            result = imports.strip_imports(self, types)
        return self.follow_path(path, result, scope)

    @debug.increase_indent
    def execute(self, obj, params=(), evaluate_generator=False):
        if obj.isinstance(er.Function):
            obj = obj.get_decorated_func()

        debug.dbg('execute: %s %s', obj, params)
        try:
            return stdlib.execute(self, obj, params)
        except stdlib.NotInStdLib:
            pass

        if isinstance(obj, iterable.GeneratorMethod):
            return obj.execute()
        elif obj.isinstance(compiled.CompiledObject):
            if obj.is_executable_class():
                return [er.Instance(self, obj, params)]
            else:
                return list(obj.execute_function(self, params))
        elif obj.isinstance(er.Class):
            # There maybe executions of executions.
            return [er.Instance(self, obj, params)]
        else:
            stmts = []
            if obj.isinstance(er.Function):
                stmts = er.FunctionExecution(self, obj, params).get_return_types(evaluate_generator)
            else:
                if hasattr(obj, 'execute_subscope_by_name'):
                    try:
                        stmts = obj.execute_subscope_by_name('__call__', params)
                    except KeyError:
                        debug.warning("no __call__ func available %s", obj)
                else:
                    debug.warning("no execution possible %s", obj)

            debug.dbg('execute result: %s in %s', stmts, obj)
            return imports.strip_imports(self, stmts)

    def goto(self, stmt, call_path):
        scope = stmt.get_parent_until(pr.IsScope)
        pos = stmt.start_pos
        call_path, search_name_part = call_path[:-1], call_path[-1]

        if call_path:
            scopes = self.eval_call_path(iter(call_path), scope, pos)
            search_global = False
            pos = None
        else:
            # TODO does this exist? i don't think so
            scopes = [scope]
            search_global = True
        follow_res = []
        for s in scopes:
            follow_res += self.find_types(s, search_name_part, pos,
                                          search_global=search_global, is_goto=True)
        return follow_res, search_name_part


def filter_private_variable(scope, call_scope, var_name):
    """private variables begin with a double underline `__`"""
    var_name = str(var_name)  # var_name could be a NamePart
    if isinstance(var_name, (str, unicode)) and isinstance(scope, er.Instance)\
            and var_name.startswith('__') and not var_name.endswith('__'):
        s = call_scope.get_parent_until((pr.Class, er.Instance, compiled.CompiledObject))
        if s != scope:
            if isinstance(scope.base, compiled.CompiledObject):
                if s != scope.base:
                    return True
            else:
                if s != scope.base.base:
                    return True
    return False


def _evaluate_list_comprehension(lc, parent=None):
    input = lc.input
    nested_lc = input.expression_list()[0]
    if isinstance(nested_lc, pr.ListComprehension):
        # is nested LC
        input = nested_lc.stmt
    module = input.get_parent_until()
    # create a for loop, which does the same as list comprehensions
    loop = pr.ForFlow(module, [input], lc.stmt.start_pos, lc.middle, True)

    loop.parent = parent or lc.get_parent_until(pr.IsScope)

    if isinstance(nested_lc, pr.ListComprehension):
        loop = _evaluate_list_comprehension(nested_lc, loop)
    return loop
