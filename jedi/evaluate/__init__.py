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
from itertools import chain

from jedi.parser import tree as pr
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
from jedi.evaluate.helpers import FakeStatement, call_of_name


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
            if isinstance(stmt.get_parent_until(pr.ForStmt), pr.ForStmt):
                # Iterate through result and add the values, that's possible
                # only in for loops without clutter, because they are
                # predictable.
                for r in types:
                    left = precedence.calculate(self, left, operator, [r])
                types = left
            else:
                types = precedence.calculate(self, left, operator, types)
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
        elif element.type == 'operator':
            # Must be an ellipsis, other operators are not evaluated.
            return []  # Ignore for now.
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

    def goto_definition(self, name):
        def_ = name.get_definition()
        if def_.type == 'expr_stmt' and name in def_.get_defined_names():
            return self.eval_statement(def_, name)
        call = call_of_name(name)
        return self.eval_element(call)

    def goto(self, name):
        def resolve_implicit_imports(names):
            for name in names:
                if isinstance(name.parent, helpers.FakeImport):
                    # Those are implicit imports.
                    s = imports.ImportWrapper(self, name)
                    for n in s.follow(is_goto=True):
                        yield n
                yield name

        stmt = name.get_definition()
        par = name.parent
        if par.type == 'argument' and par.children[1] == '=' and par.children[0] == name:
            # Named param goto.
            trailer = par.parent
            if trailer.type == 'arglist':
                trailer = trailer.parent
            if trailer.type != 'classdef':
                for i, t in enumerate(trailer.parent.children):
                    if t == trailer:
                        to_evaluate = trailer.parent.children[:i]
                types = self.eval_element(to_evaluate[0])
                for trailer in to_evaluate[1:]:
                    types = self.eval_trailer(types, trailer)
                param_names = []
                for typ in types:
                    try:
                        params = typ.params
                    except AttributeError:
                        pass
                    else:
                        param_names += [param.name for param in params
                                        if param.name.value == name.value]
                return param_names
        elif isinstance(par, pr.ExprStmt) and name in par.get_defined_names():
            # Only take the parent, because if it's more complicated than just
            # a name it's something you can "goto" again.
            return [name]
        elif isinstance(par, (pr.Param, pr.Function, pr.Class)) and par.name is name:
            return [name]
        elif isinstance(stmt, pr.Import):
            return imports.ImportWrapper(self, name).follow(is_goto=True)

        scope = name.get_parent_scope()
        if pr.is_node(name.parent, 'trailer'):
            call = call_of_name(name, cut_own_trailer=True)
            types = self.eval_element(call)
            return resolve_implicit_imports(iterable.unite(
                self.find_types(typ, name, is_goto=True) for typ in types
            ))
        else:
            return self.find_types(scope, name, stmt.start_pos,
                                   search_global=True, is_goto=True)
