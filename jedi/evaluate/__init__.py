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
import copy
from itertools import tee, chain

from jedi._compatibility import next, hasattr, unicode
from jedi.parser import tree as pr
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
from jedi.evaluate import param
from jedi.evaluate import helpers
from jedi.evaluate.helpers import FakeStatement, deep_ast_copy, call_of_name


class Evaluator(object):
    def __init__(self, grammar):
        self.grammar = grammar
        self.memoize_cache = {}  # for memoize decorators
        self.import_cache = {}  # like `sys.modules`.
        self.compiled_cache = {}  # see `compiled.create()`
        self.recursion_detector = recursion.RecursionDetector()
        self.execution_recursion_detector = recursion.ExecutionRecursionDetector()
        self.analysis = []

    def find_types(self, scope, name_str, position=None, search_global=False,
                   is_goto=False):
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
        return f.find(scopes, search_global)

    @memoize_default(default=[], evaluator_is_first_arg=True)
    @recursion.recursion_decorator
    @debug.increase_indent
    def eval_statement(self, stmt, seek_name=None):
        """
        The starting point of the completion. A statement always owns a call
        list, which are the calls, that a statement does. In case multiple
        names are defined in the statement, `seek_name` returns the result for
        this name.

        :param stmt: A `pr.ExprStmt`.
        """
        debug.dbg('eval_statement %s (%s)', stmt, seek_name)
        if isinstance(stmt, FakeStatement):
            return stmt.children  # Already contains the results.

        types = self.eval_element(stmt.get_rhs())

        if seek_name:
            types = finder.check_tuple_assignments(types, seek_name)

        first_operation = stmt.first_operation()
        if first_operation not in ('=', None) and not isinstance(stmt, er.InstanceElement):  # TODO don't check for this.
            # `=` is always the last character in aug assignments -> -1
            operator = copy.copy(first_operation)
            operator.value = operator.value[:-1]
            name = str(stmt.get_defined_names()[0])
            parent = er.wrap(self, stmt.get_parent_scope())
            left = self.find_types(parent, name, stmt.start_pos)
            # TODO REMOVE or implement
            if False          and isinstance(stmt.parent, pr.ForFlow):
                # iterate through result and add the values, that's possible
                # only in for loops without clutter, because they are
                # predictable.
                for r in types:
                    left = precedence.calculate(self, left, operator, [r])
                types = left
            else:
                types = precedence.calculate(self, left, operator, types)
        elif False and len(stmt.get_defined_names()) > 1 and seek_name and ass_details:
            # Assignment checking is only important if the statement defines
            # multiple variables.
            new_result = []
            for ass_expression_list, op in ass_details:
                new_result += finder.find_assignments(ass_expression_list[0], result, seek_name)
            result = new_result
        debug.dbg('eval_statement result %s', types)
        return types

    @memoize_default(evaluator_is_first_arg=True)
    def eval_element(self, element):
        if isinstance(element, iterable.AlreadyEvaluated):
            return element
        elif isinstance(element, iterable.MergedNodes):
            return iterable.unite(self.eval_element(e) for e in element)

        debug.dbg('eval_element %s@%s', element, element.start_pos)
        if isinstance(element, (pr.Name, pr.Literal)) or pr.is_node(element, 'atom'):
            return self._eval_atom(element)
        elif isinstance(element, pr.Keyword):
            # For False/True/None
            return [compiled.builtin.get_by_name(element.value)]
        elif element.isinstance(pr.Lambda):
            return [er.LambdaWrapper(self, element)]
        elif element.isinstance(er.LambdaWrapper):
            return [element]  # TODO this is no real evaluation.
        elif element.type == 'power':
            types = self._eval_atom(element.children[0])
            for trailer in element.children[1:]:
                if trailer == '**':  # has a power operation.
                    raise NotImplementedError
                types = self.eval_trailer(types, trailer)

            return types
        elif element.type in ('testlist_star_expr', 'testlist',):
            # The implicit tuple in statements.
            return [iterable.ImplicitTuple(self, element)]
        elif element.type in ('not_test', 'factor'):
            types = self.eval_element(element.children[-1])
            for operator in element.children[:-1]:
                types = list(precedence.factor_calculate(self, types, operator))
            return types
        elif element.type == 'test':
            # `x if foo else y` case.
            return (self.eval_element(element.children[0]) +
                    self.eval_element(element.children[-1]))
        elif element.type == 'dotted_name':
            types = self._eval_atom(element.children[0])
            for next_name in element.children[2::2]:
                types = list(chain.from_iterable(self.find_types(typ, next_name)
                                                 for typ in types))
            return types
        else:
            return precedence.calculate_children(self, element.children)

    def _eval_atom(self, atom):
        """
        Basically to process ``atom`` nodes. The parser sometimes doesn't
        generate the node (because it has just one child). In that case an atom
        might be a name or a literal as well.
        """
        if isinstance(atom, pr.Name):
            # This is the first global lookup.
            stmt = atom.get_definition()
            scope = stmt.get_parent_until(pr.IsScope, include_current=True)
            if isinstance(stmt, pr.CompFor):
                stmt = stmt.get_parent_until((pr.ClassOrFunc, pr.ExprStmt))
            return self.find_types(scope, atom, stmt.start_pos, search_global=True)
        elif isinstance(atom, pr.Literal):
            return [compiled.create(self, atom.eval())]
        else:
            c = atom.children
            # Parentheses without commas are not tuples.
            if c[0] == '(' and not len(c) == 2 \
                    and not(pr.is_node(c[1], 'testlist_comp')
                            and len(c[1].children) > 1):
                return self.eval_element(c[1])
            try:
                comp_for = c[1].children[1]
            except (IndexError, AttributeError):
                pass
            else:
                if isinstance(comp_for, pr.CompFor):
                    return [iterable.Comprehension.from_atom(self, atom)]
            return [iterable.Array(self, atom)]

    def eval_trailer(self, types, trailer):
        trailer_op, node = trailer.children[:2]
        if node == ')':  # `arglist` is optional.
            node = ()
        new_types = []
        for typ in types:
            debug.dbg('eval_trailer: %s in scope %s', trailer, typ)
            if trailer_op == '.':
                new_types += self.find_types(typ, node)
            elif trailer_op == '(':
                new_types += self.execute(typ, node, trailer)
            elif trailer_op == '[':
                try:
                    get = typ.get_index_types
                except AttributeError:
                    debug.warning("TypeError: '%s' object is not subscriptable"
                                  % typ)
                else:
                    new_types += get(self, node)
        return new_types

    def execute_evaluated(self, obj, *args):
        """
        Execute a function with already executed arguments.
        """
        args = [iterable.AlreadyEvaluated([arg]) for arg in args]
        return self.execute(obj, args)

    @debug.increase_indent
    def execute(self, obj, arguments=(), trailer=None):
        if not isinstance(arguments, param.Arguments):
            arguments = param.Arguments(self, arguments, trailer)

        if obj.isinstance(er.Function):
            obj = obj.get_decorated_func()

        debug.dbg('execute: %s %s', obj, arguments)
        try:
            # Some stdlib functions like super(), namedtuple(), etc. have been
            # hard-coded in Jedi to support them.
            return stdlib.execute(self, obj, arguments)
        except stdlib.NotInStdLib:
            pass

        try:
            func = obj.py__call__
        except AttributeError:
            debug.warning("no execution possible %s", obj)
            return []
        else:
            types = func(self, arguments)
            debug.dbg('execute result: %s in %s', types, obj)
            return types

    def eval_expression_list(self, expression_list):
        """
        `expression_list` can be either `pr.Array` or `list of list`.
        It is used to evaluate a two dimensional object, that has calls, arrays and
        operators in it.
        """
        debug.dbg('eval_expression_list: %s', expression_list)
        p = precedence.create_precedence(expression_list)
        return precedence.process_precedence_element(self, p) or []

    def eval_statement_element(self, element):
        if isinstance(element, pr.ListComprehension):
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
        elif isinstance(element, Token):
            return []
        else:
            return self.eval_call(element)

    def eval_call(self, call):
        """Follow a call is following a function, variable, string, etc."""
        path = call.generate_call_path()

        # find the statement of the Scope
        s = call
        while not s.parent.is_scope():
            s = s.parent
        scope = s.parent
        return self.eval_call_path(path, scope, s.start_pos)

    def eval_call_path(self, path, scope, position):
        """
        Follows a path generated by `pr.StatementElement.generate_call_path()`.
        """
        current = next(path)

        if isinstance(current, pr.Array):
            if current.type == pr.Array.NOARRAY:
                try:
                    lst_cmp = current[0].expression_list()[0]
                    if not isinstance(lst_cmp, pr.ListComprehension):
                        raise IndexError
                except IndexError:
                    types = list(chain.from_iterable(self.eval_statement(s)
                                                     for s in current))
                else:
                    types = [iterable.GeneratorComprehension(self, lst_cmp)]
            else:
                types = [iterable.Array(self, current)]
        else:
            if isinstance(current, pr.Name):
                # This is the first global lookup.
                types = self.find_types(scope, current, position=position,
                                        search_global=True)
            else:
                # for pr.Literal
                types = [compiled.create(self, current.value)]
            types = imports.follow_imports(self, types)

        return self.follow_path(path, types, scope)

    def follow_path(self, path, types, call_scope):
        """
        Follows a path like::

            self.follow_path(iter(['Foo', 'bar']), [a_type], from_somewhere)

        to follow a call like ``module.a_type.Foo.bar`` (in ``from_somewhere``).
        """
        results_new = []
        iter_paths = tee(path, len(types))

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
                    if isinstance(typ, compiled.CompiledObject):
                        # CompiledObject doesn't contain an evaluator instance.
                        result = typ.get_index_types(self, current)
                    else:
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
            types = self.find_types(typ, current)
            result = imports.follow_imports(self, types)
        return self.follow_path(path, result, scope)

    @debug.increase_indent
    def execute_old(self, obj, params=()):
        if obj.isinstance(er.Function):
            obj = obj.get_decorated_func()

        debug.dbg('execute: %s %s', obj, params)
        try:
            # Some stdlib functions like super(), namedtuple(), etc. have been
            # hard-coded in Jedi to support them.
            return stdlib.execute(self, obj, params)
        except stdlib.NotInStdLib:
            pass

        try:
            func = obj.py__call__
        except AttributeError:
            debug.warning("no execution possible %s", obj)
            return []
        else:
            types = func(self, params)
            debug.dbg('execute result: %s in %s', types, obj)
            return types

    def goto_definition(self, name):
        call = call_of_name(name)
        return self.eval_element(call)

    def goto(self, name):
        def resolve_implicit_imports(names):
            for name in names:
                if isinstance(name, helpers.FakeName):
                    # Those are implicit imports.
                    s = imports.ImportWrapper(self, name)
                    for n in s.follow(is_goto=True):
                        yield n
                yield name

        imp = name.get_definition()
        stmt = name.parent
        if isinstance(stmt, pr.ExprStmt) and name in stmt.get_defined_names():
            # TODO remove? I think this is never called.
            return [name]
        elif isinstance(stmt, (pr.Param, pr.Function, pr.Class)) and stmt.name is name:
            return [name]
        elif isinstance(imp, pr.Import):
            return imports.ImportWrapper(self, name).follow(is_goto=True)

        scope = name.get_parent_scope()
        if pr.is_node(name.parent, 'trailer'):
            call = call_of_name(name, cut_own_trailer=True)
            types = self.eval_element(call)
            return resolve_implicit_imports(iterable.unite(
                self.find_types(typ, name, is_goto=True) for typ in types
            ))
        else:
            return self.find_types(scope, name, name.start_pos,
                                   search_global=True, is_goto=True)


        if isinstance(stmt, pr.Import):
            # Nowhere to goto for aliases
            if stmt.alias == call_path[0]:
                return [call_path[0]]

            names = stmt.get_all_import_names()
            if stmt.alias:
                names = names[:-1]
            # Filter names that are after our Name
            removed_names = len(names) - names.index(call_path[0]) - 1
            i = imports.ImportWrapper(self, stmt, kill_count=removed_names,
                                      nested_resolve=True)
            return i.follow(is_goto=True)

        # Return the name defined in the call_path, if it's part of the
        # statement name definitions. Only return, if it's one name and one
        # name only. Otherwise it's a mixture between a definition and a
        # reference. In this case it's just a definition. So we stay on it.
        if len(call_path) == 1 and isinstance(call_path[0], pr.Name) \
                and call_path[0] in stmt.get_defined_names():
            # Named params should get resolved to their param definitions.
            if pr.Array.is_type(stmt.parent, pr.Array.TUPLE, pr.Array.NOARRAY) \
                    and stmt.parent.previous:
                call = deep_ast_copy(stmt.parent.previous)
                # We have made a copy, so we're fine to change it.
                call.next = None
                while call.previous is not None:
                    call = call.previous
                param_names = []
                named_param_name = stmt.get_defined_names()[0]
                for typ in self.eval_call(call):
                    if isinstance(typ, er.Class):
                        params = []
                        for init_method in typ.py__getattribute__('__init__'):
                            params += init_method.params
                    else:
                        params = typ.params
                    for param in params:
                        if unicode(param.get_name()) == unicode(named_param_name):
                            param_names.append(param.get_name())
                return param_names
            return [call_path[0]]

        scope = stmt.get_parent_scope()
        pos = stmt.start_pos
        first_part, search_name_part = call_path[:-1], call_path[-1]

        if first_part:
            scopes = self.eval_call_path(iter(first_part), scope, pos)
            search_global = False
            pos = None
        else:
            scopes = [scope]
            search_global = True

        follow_res = []
        for s in scopes:
            follow_res += self.find_types(s, search_name_part, pos,
                                          search_global=search_global, is_goto=True)
        return follow_res
