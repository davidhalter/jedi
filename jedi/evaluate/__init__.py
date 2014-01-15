"""
Evaluation of Python code in |jedi| is based on three assumptions:

* Code is recursive (to weaken this assumption, the :mod:`dynamic` module
  exists).
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

- follow import, which happens in the :mod:`imports` module.
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
import sys
import itertools

from jedi._compatibility import next, hasattr, unicode, reraise
from jedi import common
from jedi.parser import representation as pr
from jedi import debug
from jedi.evaluate import representation as er
from jedi.evaluate import imports
from jedi.evaluate import recursion
from jedi.evaluate import iterable
from jedi.evaluate.cache import memoize_default
from jedi.evaluate import stdlib
from jedi.evaluate import finder
from jedi.evaluate import compiled


class Evaluator(object):
    def __init__(self):
        self.memoize_cache = {}  # for memoize decorators
        self.recursion_detector = recursion.RecursionDetector()
        self.execution_recursion_detector = recursion.ExecutionRecursionDetector()

    def get_names_of_scope(self, scope, position=None, star_search=True,
                           include_builtin=True):
        """
        Get all completions (names) possible for the current scope.
        The star search option is only here to provide an optimization. Otherwise
        the whole thing would probably start a little recursive madness.

        This function is used to include names from outer scopes.  For example,
        when the current scope is function:

        >>> from jedi.parser import Parser
        >>> parser = Parser('''
        ... x = ['a', 'b', 'c']
        ... def func():
        ...     y = None
        ... ''')
        >>> scope = parser.module.subscopes[0]
        >>> scope
        <Function: func@3-4>

        `get_names_of_scope` is a generator.  First it yields names from
        most inner scope.

        >>> pairs = list(Evaluator().get_names_of_scope(scope))
        >>> pairs[0]
        (<Function: func@3-4>, [<Name: y@4,4>])

        Then it yield the names from one level outer scope.  For this
        example, this is the most outer scope.

        >>> pairs[1]
        (<SubModule: None@1-4>, [<Name: x@2,0>, <Name: func@3,4>])

        Finally, it yields names from builtin, if `include_builtin` is
        true (default).

        >>> pairs[2]                                        #doctest: +ELLIPSIS
        (<Builtin: ...builtin...>, [<CompiledName: ...>, ...])

        :rtype: [(pr.Scope, [pr.Name])]
        :return: Return an generator that yields a pair of scope and names.
        """
        in_func_scope = scope
        non_flow = scope.get_parent_until(pr.Flow, reverse=True)
        while scope:
            if isinstance(scope, pr.SubModule) and scope.parent:
                # we don't want submodules to report if we have modules.
                scope = scope.parent
                continue
            # `pr.Class` is used, because the parent is never `Class`.
            # Ignore the Flows, because the classes and functions care for that.
            # InstanceElement of Class is ignored, if it is not the start scope.
            if not (scope != non_flow and scope.isinstance(pr.Class)
                    or scope.isinstance(pr.Flow)
                    or scope.isinstance(er.Instance)
                    and non_flow.isinstance(er.Function)
                    or isinstance(scope, compiled.CompiledObject)
                    and scope.type() == 'class' and in_func_scope != scope):
                try:
                    if isinstance(scope, er.Instance):
                        for g in scope.scope_generator():
                            yield g
                    else:
                        yield scope, finder._get_defined_names_for_position(scope, position, in_func_scope)
                except StopIteration:
                    reraise(common.MultiLevelStopIteration, sys.exc_info()[2])
            if scope.isinstance(pr.ForFlow) and scope.is_list_comp:
                # is a list comprehension
                yield scope, scope.get_set_vars(is_internal_call=True)

            scope = scope.parent
            # This is used, because subscopes (Flow scopes) would distort the
            # results.
            if scope and scope.isinstance(er.Function, pr.Function, er.FunctionExecution):
                in_func_scope = scope

        # Add star imports.
        if star_search:
            for s in imports.remove_star_imports(self, non_flow.get_parent_until()):
                for g in self.get_names_of_scope(s, star_search=False):
                    yield g

            # Add builtins to the global scope.
            if include_builtin:
                yield compiled.builtin, compiled.builtin.get_defined_names()

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

    @memoize_default(default=(), evaluator_is_first_arg=True)
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

        # Assignment checking is only important if the statement defines multiple
        # variables.
        if len(stmt.get_set_vars()) > 1 and seek_name and stmt.assignment_details:
            new_result = []
            for ass_expression_list, op in stmt.assignment_details:
                new_result += _find_assignments(ass_expression_list[0], result, seek_name)
            result = new_result
        return set(result)

    def eval_expression_list(self, expression_list, follow_array=False):
        """
        `expression_list` can be either `pr.Array` or `list of list`.
        It is used to evaluate a two dimensional object, that has calls, arrays and
        operators in it.
        """
        def evaluate_list_comprehension(lc, parent=None):
            input = lc.input
            nested_lc = lc.input.token_list[0]
            if isinstance(nested_lc, pr.ListComprehension):
                # is nested LC
                input = nested_lc.stmt
            module = input.get_parent_until()
            # create a for loop, which does the same as list comprehensions
            loop = pr.ForFlow(module, [input], lc.stmt.start_pos, lc.middle, True)

            loop.parent = parent or lc.get_parent_until(pr.IsScope)

            if isinstance(nested_lc, pr.ListComprehension):
                loop = evaluate_list_comprehension(nested_lc, loop)
            return loop

        debug.dbg('eval_expression_list: %s', expression_list)
        result = []
        calls_iterator = iter(expression_list)
        for call in calls_iterator:
            if pr.Array.is_type(call, pr.Array.NOARRAY):
                r = list(itertools.chain.from_iterable(self.eval_statement(s)
                                                       for s in call))
                call_path = call.generate_call_path()
                next(call_path, None)  # the first one has been used already
                result += self.follow_path(call_path, r, call.parent,
                                           position=call.start_pos)
            elif isinstance(call, pr.ListComprehension):
                loop = evaluate_list_comprehension(call)
                # Caveat: parents are being changed, but this doesn't matter,
                # because nothing else uses it.
                call.stmt.parent = loop
                result += self.eval_statement(call.stmt)
            else:
                if isinstance(call, pr.Lambda):
                    result.append(er.Function(self, call))
                # With things like params, these can also be functions...
                elif isinstance(call, pr.Base) and call.isinstance(
                        er.Function, er.Class, er.Instance, iterable.ArrayInstance):
                    result.append(call)
                # The string tokens are just operations (+, -, etc.)
                elif isinstance(call, compiled.CompiledObject):
                    result.append(call)
                elif not isinstance(call, (str, unicode)):
                    if isinstance(call, pr.Call) and str(call.name) == 'if':
                        # Ternary operators.
                        while True:
                            try:
                                call = next(calls_iterator)
                            except StopIteration:
                                break
                            with common.ignored(AttributeError):
                                if str(call.name) == 'else':
                                    break
                        continue
                    result += self.eval_call(call)
                elif call == '*':
                    if [r for r in result if isinstance(r, iterable.Array)
                            or isinstance(r, compiled.CompiledObject)
                            and isinstance(r.obj, (str, unicode))]:
                        # if it is an iterable, ignore * operations
                        next(calls_iterator)
        return set(result)

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
                types = [compiled.create(current.value)]
            types = imports.strip_imports(self, types)

        return self.follow_path(path, types, scope, position=position)

    def follow_path(self, path, types, call_scope, position=None):
        """
        Follows a path like::

            self.follow_path(iter(['Foo', 'bar']), [a_type], from_somewhere)

        to follow a call like ``module.a_type.Foo.bar`` (in ``from_somewhere``).
        """
        results_new = []
        iter_paths = itertools.tee(path, len(types))

        for i, typ in enumerate(types):
            fp = self._follow_path(iter_paths[i], typ, call_scope, position=position)
            if fp is not None:
                results_new += fp
            else:
                # This means stop iteration.
                return types
        return results_new

    def _follow_path(self, path, typ, scope, position=None):
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
                    result = typ.get_index_types(current)
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
            types = self.find_types(typ, current, position=position)
            result = imports.strip_imports(self, types)
        return self.follow_path(path, set(result), scope, position=position)

    @debug.increase_indent
    def execute(self, obj, params=(), evaluate_generator=False):
        if obj.isinstance(er.Function):
            obj = obj.get_decorated_func()

        debug.dbg('execute: %s %s', obj, params)
        try:
            return stdlib.execute(self, obj, params)
        except stdlib.NotInStdLib:
            pass

        if obj.isinstance(compiled.CompiledObject):
            if obj.is_executable_class():
                return [er.Instance(self, obj, params)]
            else:
                return list(obj.execute_function(self, params))
        elif obj.isinstance(er.Class):
            # There maybe executions of executions.
            return [er.Instance(self, obj, params)]
        elif isinstance(obj, iterable.Generator):
            return obj.iter_content()
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

    def goto(self, stmt, call_path=None):
        if call_path is None:
            expression_list = stmt.expression_list()
            if len(expression_list) == 0:
                return [], ''
            # Only the first command is important, the rest should basically not
            # happen except in broken code (e.g. docstrings that aren't code).
            call = expression_list[0]
            if isinstance(call, (str, unicode)):
                call_path = [call]
            else:
                call_path = list(call.generate_call_path())

        scope = stmt.get_parent_until(pr.IsScope)
        pos = stmt.start_pos
        call_path, search = call_path[:-1], call_path[-1]
        pos = pos[0], pos[1] + 1

        if call_path:
            scopes = self.eval_call_path(iter(call_path), scope, pos)
            search_global = False
            pos = None
        else:
            scopes = [scope]
            search_global = True
        follow_res = []
        for s in scopes:
            follow_res += self.find_types(s, search, pos,
                                          search_global=search_global, is_goto=True)
        return follow_res, search


def filter_private_variable(scope, call_scope, var_name):
    """private variables begin with a double underline `__`"""
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


def _assign_tuples(tup, results, seek_name):
    """
    This is a normal assignment checker. In python functions and other things
    can return tuples:
    >>> a, b = 1, ""
    >>> a, (b, c) = 1, ("", 1.0)

    Here, if `seek_name` is "a", the number type will be returned.
    The first part (before `=`) is the param tuples, the second one result.

    :type tup: pr.Array
    """
    def eval_results(index):
        types = []
        for r in results:
            try:
                func = r.get_exact_index_types
            except AttributeError:
                debug.warning("invalid tuple lookup %s of result %s in %s",
                              tup, results, seek_name)
            else:
                with common.ignored(IndexError):
                    types += func(index)
        return types

    result = []
    for i, stmt in enumerate(tup):
        # Used in assignments. There is just one call and no other things,
        # therefore we can just assume, that the first part is important.
        command = stmt.expression_list()[0]

        if tup.type == pr.Array.NOARRAY:

                # unnessecary braces -> just remove.
            r = results
        else:
            r = eval_results(i)

        # LHS of tuples can be nested, so resolve it recursively
        result += _find_assignments(command, r, seek_name)
    return result


def _find_assignments(lhs, results, seek_name):
    """
    Check if `seek_name` is in the left hand side `lhs` of assignment.

    `lhs` can simply be a variable (`pr.Call`) or a tuple/list (`pr.Array`)
    representing the following cases::

        a = 1        # lhs is pr.Call
        (a, b) = 2   # lhs is pr.Array

    :type lhs: pr.Call
    :type results: list
    :type seek_name: str
    """
    if isinstance(lhs, pr.Array):
        return _assign_tuples(lhs, results, seek_name)
    elif lhs.name.names[-1] == seek_name:
        return results
    else:
        return []
