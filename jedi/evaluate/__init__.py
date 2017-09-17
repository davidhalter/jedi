"""
Evaluation of Python code in |jedi| is based on three assumptions:

* The code uses as least side effects as possible. Jedi understands certain
  list/tuple/set modifications, but there's no guarantee that Jedi detects
  everything (list.append in different modules for example).
* No magic is being used:

  - metaclasses
  - ``setattr()`` / ``__import__()``
  - writing to ``globals()``, ``locals()``, ``object.__dict__``
* The programmer is not a total dick, e.g. like `this
  <https://github.com/davidhalter/jedi/issues/24>`_ :-)

The actual algorithm is based on a principle called lazy evaluation. If you
don't know about it, google it.  That said, the typical entry point for static
analysis is calling ``eval_statement``. There's separate logic for
autocompletion in the API, the evaluator is all about evaluating an expression.

Now you need to understand what follows after ``eval_statement``. Let's
make an example::

    import datetime
    datetime.date.toda# <-- cursor here

First of all, this module doesn't care about completion. It really just cares
about ``datetime.date``. At the end of the procedure ``eval_statement`` will
return the ``date`` class.

To *visualize* this (simplified):

- ``Evaluator.eval_statement`` doesn't do much, because there's no assignment.
- ``Evaluator.eval_element`` cares for resolving the dotted path
- ``Evaluator.find_types`` searches for global definitions of datetime, which
  it finds in the definition of an import, by scanning the syntax tree.
- Using the import logic, the datetime module is found.
- Now ``find_types`` is called again by ``eval_element`` to find ``date``
  inside the datetime module.

Now what would happen if we wanted ``datetime.date.foo.bar``? Two more
calls to ``find_types``. However the second call would be ignored, because the
first one would return nothing (there's no foo attribute in ``date``).

What if the import would contain another ``ExprStmt`` like this::

    from foo import bar
    Date = bar.baz

Well... You get it. Just another ``eval_statement`` recursion. It's really
easy. Python can obviously get way more complicated then this. To understand
tuple assignments, list comprehensions and everything else, a lot more code had
to be written.

Jedi has been tested very well, so you can just start modifying code. It's best
to write your own test first for your "new" feature. Don't be scared of
breaking stuff. As long as the tests pass, you're most likely to be fine.

I need to mention now that lazy evaluation is really good because it
only *evaluates* what needs to be *evaluated*. All the statements and modules
that are not used are just being ignored.
"""

import copy
import sys

from parso.python import tree
import parso

from jedi import debug
from jedi.common import unite
from jedi.evaluate import representation as er
from jedi.evaluate import imports
from jedi.evaluate import recursion
from jedi.evaluate import iterable
from jedi.evaluate.cache import evaluator_function_cache
from jedi.evaluate import stdlib
from jedi.evaluate import finder
from jedi.evaluate import compiled
from jedi.evaluate import precedence
from jedi.evaluate import param
from jedi.evaluate import helpers
from jedi.evaluate import pep0484
from jedi.evaluate.filters import TreeNameDefinition, ParamName
from jedi.evaluate.instance import AnonymousInstance, BoundMethod
from jedi.evaluate.context import ContextualizedName, ContextualizedNode
from jedi import parser_utils


def _limit_context_infers(func):
    """
    This is for now the way how we limit type inference going wild. There are
    other ways to ensure recursion limits as well. This is mostly necessary
    because of instance (self) access that can be quite tricky to limit.

    I'm still not sure this is the way to go, but it looks okay for now and we
    can still go anther way in the future. Tests are there. ~ dave
    """
    def wrapper(evaluator, context, *args, **kwargs):
        n = context.tree_node
        try:
            evaluator.inferred_element_counts[n] += 1
            if evaluator.inferred_element_counts[n] > 300:
                debug.warning('In context %s there were too many inferences.', n)
                return set()
        except KeyError:
            evaluator.inferred_element_counts[n] = 1
        return func(evaluator, context, *args, **kwargs)

    return wrapper


class Evaluator(object):
    def __init__(self, grammar, sys_path=None):
        self.grammar = grammar
        self.latest_grammar = parso.load_grammar(version='3.6')
        self.memoize_cache = {}  # for memoize decorators
        # To memorize modules -> equals `sys.modules`.
        self.modules = {}  # like `sys.modules`.
        self.compiled_cache = {}  # see `evaluate.compiled.create()`
        self.inferred_element_counts = {}
        self.mixed_cache = {}  # see `evaluate.compiled.mixed._create()`
        self.analysis = []
        self.dynamic_params_depth = 0
        self.is_analysis = False
        self.python_version = sys.version_info[:2]

        if sys_path is None:
            sys_path = sys.path
        self.sys_path = copy.copy(sys_path)
        try:
            self.sys_path.remove('')
        except ValueError:
            pass

        self.reset_recursion_limitations()

        # Constants
        self.BUILTINS = compiled.get_special_object(self, 'BUILTINS')

    def reset_recursion_limitations(self):
        self.recursion_detector = recursion.RecursionDetector()
        self.execution_recursion_detector = recursion.ExecutionRecursionDetector(self)

    def find_types(self, context, name_or_str, name_context, position=None,
                   search_global=False, is_goto=False, analysis_errors=True):
        """
        This is the search function. The most important part to debug.
        `remove_statements` and `filter_statements` really are the core part of
        this completion.

        :param position: Position of the last statement -> tuple of line, column
        :return: List of Names. Their parents are the types.
        """
        f = finder.NameFinder(self, context, name_context, name_or_str,
                              position, analysis_errors=analysis_errors)
        filters = f.get_filters(search_global)
        if is_goto:
            return f.filter_name(filters)
        return f.find(filters, attribute_lookup=not search_global)

    @_limit_context_infers
    def eval_statement(self, context, stmt, seek_name=None):
        with recursion.execution_allowed(self, stmt) as allowed:
            if allowed or context.get_root_context() == self.BUILTINS:
                return self._eval_stmt(context, stmt, seek_name)
        return set()

    #@evaluator_function_cache(default=[])
    @debug.increase_indent
    def _eval_stmt(self, context, stmt, seek_name=None):
        """
        The starting point of the completion. A statement always owns a call
        list, which are the calls, that a statement does. In case multiple
        names are defined in the statement, `seek_name` returns the result for
        this name.

        :param stmt: A `tree.ExprStmt`.
        """
        debug.dbg('eval_statement %s (%s)', stmt, seek_name)
        rhs = stmt.get_rhs()
        types = self.eval_element(context, rhs)

        if seek_name:
            c_node = ContextualizedName(context, seek_name)
            types = finder.check_tuple_assignments(self, c_node, types)

        first_operator = next(stmt.yield_operators(), None)
        if first_operator not in ('=', None) and first_operator.type == 'operator':
            # `=` is always the last character in aug assignments -> -1
            operator = copy.copy(first_operator)
            operator.value = operator.value[:-1]
            name = stmt.get_defined_names()[0].value
            left = context.py__getattribute__(
                name, position=stmt.start_pos, search_global=True)

            for_stmt = tree.search_ancestor(stmt, 'for_stmt')
            if for_stmt is not None and for_stmt.type == 'for_stmt' and types \
                    and parser_utils.for_stmt_defines_one_name(for_stmt):
                # Iterate through result and add the values, that's possible
                # only in for loops without clutter, because they are
                # predictable. Also only do it, if the variable is not a tuple.
                node = for_stmt.get_testlist()
                cn = ContextualizedNode(context, node)
                ordered = list(iterable.py__iter__(self, cn.infer(), cn))

                for lazy_context in ordered:
                    dct = {for_stmt.children[1].value: lazy_context.infer()}
                    with helpers.predefine_names(context, for_stmt, dct):
                        t = self.eval_element(context, rhs)
                        left = precedence.calculate(self, context, left, operator, t)
                types = left
            else:
                types = precedence.calculate(self, context, left, operator, types)
        debug.dbg('eval_statement result %s', types)
        return types

    def eval_element(self, context, element):
        if isinstance(context, iterable.CompForContext):
            return self._eval_element_not_cached(context, element)

        if_stmt = element
        while if_stmt is not None:
            if_stmt = if_stmt.parent
            if if_stmt.type in ('if_stmt', 'for_stmt'):
                break
            if parser_utils.is_scope(if_stmt):
                if_stmt = None
                break
        predefined_if_name_dict = context.predefined_names.get(if_stmt)
        if predefined_if_name_dict is None and if_stmt and if_stmt.type == 'if_stmt':
            if_stmt_test = if_stmt.children[1]
            name_dicts = [{}]
            # If we already did a check, we don't want to do it again -> If
            # context.predefined_names is filled, we stop.
            # We don't want to check the if stmt itself, it's just about
            # the content.
            if element.start_pos > if_stmt_test.end_pos:
                # Now we need to check if the names in the if_stmt match the
                # names in the suite.
                if_names = helpers.get_names_of_node(if_stmt_test)
                element_names = helpers.get_names_of_node(element)
                str_element_names = [e.value for e in element_names]
                if any(i.value in str_element_names for i in if_names):
                    for if_name in if_names:
                        definitions = self.goto_definitions(context, if_name)
                        # Every name that has multiple different definitions
                        # causes the complexity to rise. The complexity should
                        # never fall below 1.
                        if len(definitions) > 1:
                            if len(name_dicts) * len(definitions) > 16:
                                debug.dbg('Too many options for if branch evaluation %s.', if_stmt)
                                # There's only a certain amount of branches
                                # Jedi can evaluate, otherwise it will take to
                                # long.
                                name_dicts = [{}]
                                break

                            original_name_dicts = list(name_dicts)
                            name_dicts = []
                            for definition in definitions:
                                new_name_dicts = list(original_name_dicts)
                                for i, name_dict in enumerate(new_name_dicts):
                                    new_name_dicts[i] = name_dict.copy()
                                    new_name_dicts[i][if_name.value] = set([definition])

                                name_dicts += new_name_dicts
                        else:
                            for name_dict in name_dicts:
                                name_dict[if_name.value] = definitions
            if len(name_dicts) > 1:
                result = set()
                for name_dict in name_dicts:
                    with helpers.predefine_names(context, if_stmt, name_dict):
                        result |= self._eval_element_not_cached(context, element)
                return result
            else:
                return self._eval_element_if_evaluated(context, element)
        else:
            if predefined_if_name_dict:
                return self._eval_element_not_cached(context, element)
            else:
                return self._eval_element_if_evaluated(context, element)

    def _eval_element_if_evaluated(self, context, element):
        """
        TODO This function is temporary: Merge with eval_element.
        """
        parent = element
        while parent is not None:
            parent = parent.parent
            predefined_if_name_dict = context.predefined_names.get(parent)
            if predefined_if_name_dict is not None:
                return self._eval_element_not_cached(context, element)
        return self._eval_element_cached(context, element)

    @evaluator_function_cache(default=set())
    def _eval_element_cached(self, context, element):
        return self._eval_element_not_cached(context, element)

    @debug.increase_indent
    @_limit_context_infers
    def _eval_element_not_cached(self, context, element):
        debug.dbg('eval_element %s@%s', element, element.start_pos)
        types = set()
        typ = element.type
        if typ in ('name', 'number', 'string', 'atom'):
            types = self.eval_atom(context, element)
        elif typ == 'keyword':
            # For False/True/None
            if element.value in ('False', 'True', 'None'):
                types.add(compiled.builtin_from_name(self, element.value))
            # else: print e.g. could be evaluated like this in Python 2.7
        elif typ == 'lambdef':
            types = set([er.FunctionContext(self, context, element)])
        elif typ == 'expr_stmt':
            types = self.eval_statement(context, element)
        elif typ in ('power', 'atom_expr'):
            first_child = element.children[0]
            if not (first_child.type == 'keyword' and first_child.value == 'await'):
                types = self.eval_atom(context, first_child)
                for trailer in element.children[1:]:
                    if trailer == '**':  # has a power operation.
                        right = self.eval_element(context, element.children[2])
                        types = set(precedence.calculate(self, context, types, trailer, right))
                        break
                    types = self.eval_trailer(context, types, trailer)
        elif typ in ('testlist_star_expr', 'testlist',):
            # The implicit tuple in statements.
            types = set([iterable.SequenceLiteralContext(self, context, element)])
        elif typ in ('not_test', 'factor'):
            types = self.eval_element(context, element.children[-1])
            for operator in element.children[:-1]:
                types = set(precedence.factor_calculate(self, types, operator))
        elif typ == 'test':
            # `x if foo else y` case.
            types = (self.eval_element(context, element.children[0]) |
                     self.eval_element(context, element.children[-1]))
        elif typ == 'operator':
            # Must be an ellipsis, other operators are not evaluated.
            # In Python 2 ellipsis is coded as three single dot tokens, not
            # as one token 3 dot token.
            assert element.value in ('.', '...')
            types = set([compiled.create(self, Ellipsis)])
        elif typ == 'dotted_name':
            types = self.eval_atom(context, element.children[0])
            for next_name in element.children[2::2]:
                # TODO add search_global=True?
                types = unite(
                    typ.py__getattribute__(next_name, name_context=context)
                    for typ in types
                )
            types = types
        elif typ == 'eval_input':
            types = self._eval_element_not_cached(context, element.children[0])
        elif typ == 'annassign':
            types = pep0484._evaluate_for_annotation(context, element.children[1])
        else:
            types = precedence.calculate_children(self, context, element.children)
        debug.dbg('eval_element result %s', types)
        return types

    def eval_atom(self, context, atom):
        """
        Basically to process ``atom`` nodes. The parser sometimes doesn't
        generate the node (because it has just one child). In that case an atom
        might be a name or a literal as well.
        """
        if atom.type == 'name':
            # This is the first global lookup.
            stmt = tree.search_ancestor(
                atom, 'expr_stmt', 'lambdef'
            ) or atom
            if stmt.type == 'lambdef':
                stmt = atom
            return context.py__getattribute__(
                name_or_str=atom,
                position=stmt.start_pos,
                search_global=True
            )
        elif isinstance(atom, tree.Literal):
            string = parser_utils.safe_literal_eval(atom.value)
            return set([compiled.create(self, string)])
        else:
            c = atom.children
            if c[0].type == 'string':
                # Will be one string.
                types = self.eval_atom(context, c[0])
                for string in c[1:]:
                    right = self.eval_atom(context, string)
                    types = precedence.calculate(self, context, types, '+', right)
                return types
            # Parentheses without commas are not tuples.
            elif c[0] == '(' and not len(c) == 2 \
                    and not(c[1].type == 'testlist_comp' and
                            len(c[1].children) > 1):
                return self.eval_element(context, c[1])

            try:
                comp_for = c[1].children[1]
            except (IndexError, AttributeError):
                pass
            else:
                if comp_for == ':':
                    # Dict comprehensions have a colon at the 3rd index.
                    try:
                        comp_for = c[1].children[3]
                    except IndexError:
                        pass

                if comp_for.type == 'comp_for':
                    return set([iterable.Comprehension.from_atom(self, context, atom)])

            # It's a dict/list/tuple literal.
            array_node = c[1]
            try:
                array_node_c = array_node.children
            except AttributeError:
                array_node_c = []
            if c[0] == '{' and (array_node == '}' or ':' in array_node_c):
                context = iterable.DictLiteralContext(self, context, atom)
            else:
                context = iterable.SequenceLiteralContext(self, context, atom)
            return set([context])

    def eval_trailer(self, context, types, trailer):
        trailer_op, node = trailer.children[:2]
        if node == ')':  # `arglist` is optional.
            node = ()

        new_types = set()
        if trailer_op == '[':
            new_types |= iterable.py__getitem__(self, context, types, trailer)
        else:
            for typ in types:
                debug.dbg('eval_trailer: %s in scope %s', trailer, typ)
                if trailer_op == '.':
                    new_types |= typ.py__getattribute__(
                        name_context=context,
                        name_or_str=node
                    )
                elif trailer_op == '(':
                    arguments = param.TreeArguments(self, context, node, trailer)
                    new_types |= self.execute(typ, arguments)
        return new_types

    @debug.increase_indent
    def execute(self, obj, arguments):
        if self.is_analysis:
            arguments.eval_all()

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
            return set()
        else:
            types = func(arguments)
            debug.dbg('execute result: %s in %s', types, obj)
            return types

    def goto_definitions(self, context, name):
        def_ = name.get_definition(import_name_always=True)
        if def_ is not None:
            type_ = def_.type
            if type_ == 'classdef':
                return [er.ClassContext(self, name.parent, context)]
            elif type_ == 'funcdef':
                return [er.FunctionContext(self, context, name.parent)]

            if type_ == 'expr_stmt':
                is_simple_name = name.parent.type not in ('power', 'trailer')
                if is_simple_name:
                    return self.eval_statement(context, def_, name)
            if type_ == 'for_stmt':
                container_types = self.eval_element(context, def_.children[3])
                cn = ContextualizedNode(context, def_.children[3])
                for_types = iterable.py__iter__types(self, container_types, cn)
                c_node = ContextualizedName(context, name)
                return finder.check_tuple_assignments(self, c_node, for_types)
            if type_ in ('import_from', 'import_name'):
                return imports.infer_import(context, name)

        return helpers.evaluate_call_of_leaf(context, name)

    def goto(self, context, name):
        definition = name.get_definition(import_name_always=True)
        if definition is not None:
            type_ = definition.type
            if type_ == 'expr_stmt':
                # Only take the parent, because if it's more complicated than just
                # a name it's something you can "goto" again.
                is_simple_name = name.parent.type not in ('power', 'trailer')
                if is_simple_name:
                    return [TreeNameDefinition(context, name)]
            elif type_ == 'param':
                return [ParamName(context, name)]
            elif type_ in ('funcdef', 'classdef'):
                return [TreeNameDefinition(context, name)]
            elif type_ in ('import_from', 'import_name'):
                module_names = imports.infer_import(context, name, is_goto=True)
                return module_names

        par = name.parent
        typ = par.type
        if typ == 'argument' and par.children[1] == '=' and par.children[0] == name:
            # Named param goto.
            trailer = par.parent
            if trailer.type == 'arglist':
                trailer = trailer.parent
            if trailer.type != 'classdef':
                if trailer.type == 'decorator':
                    types = self.eval_element(context, trailer.children[1])
                else:
                    i = trailer.parent.children.index(trailer)
                    to_evaluate = trailer.parent.children[:i]
                    types = self.eval_element(context, to_evaluate[0])
                    for trailer in to_evaluate[1:]:
                        types = self.eval_trailer(context, types, trailer)
                param_names = []
                for typ in types:
                    try:
                        get_param_names = typ.get_param_names
                    except AttributeError:
                        pass
                    else:
                        for param_name in get_param_names():
                            if param_name.string_name == name.value:
                                param_names.append(param_name)
                return param_names
        elif typ == 'dotted_name':  # Is a decorator.
            index = par.children.index(name)
            if index > 0:
                new_dotted = helpers.deep_ast_copy(par)
                new_dotted.children[index - 1:] = []
                values = self.eval_element(context, new_dotted)
                return unite(
                    value.py__getattribute__(name, name_context=context, is_goto=True)
                    for value in values
                )

        if typ == 'trailer' and par.children[0] == '.':
            values = helpers.evaluate_call_of_leaf(context, name, cut_own_trailer=True)
            return unite(
                value.py__getattribute__(name, name_context=context, is_goto=True)
                for value in values
            )
        else:
            stmt = tree.search_ancestor(
                name, 'expr_stmt', 'lambdef'
            ) or name
            if stmt.type == 'lambdef':
                stmt = name
            return context.py__getattribute__(
                name,
                position=stmt.start_pos,
                search_global=True, is_goto=True
            )

    def create_context(self, base_context, node, node_is_context=False, node_is_object=False):
        def parent_scope(node):
            while True:
                node = node.parent

                if parser_utils.is_scope(node):
                    return node
                elif node.type in ('argument', 'testlist_comp'):
                    if node.children[1].type == 'comp_for':
                        return node.children[1]
                elif node.type == 'dictorsetmaker':
                    for n in node.children[1:4]:
                        # In dictionaries it can be pretty much anything.
                        if n.type == 'comp_for':
                            return n

        def from_scope_node(scope_node, child_is_funcdef=None, is_nested=True, node_is_object=False):
            if scope_node == base_node:
                return base_context

            is_funcdef = scope_node.type in ('funcdef', 'lambdef')
            parent_scope = parser_utils.get_parent_scope(scope_node)
            parent_context = from_scope_node(parent_scope, child_is_funcdef=is_funcdef)

            if is_funcdef:
                if isinstance(parent_context, AnonymousInstance):
                    func = BoundMethod(
                        self, parent_context, parent_context.class_context,
                        parent_context.parent_context, scope_node
                    )
                else:
                    func = er.FunctionContext(
                        self,
                        parent_context,
                        scope_node
                    )
                if is_nested and not node_is_object:
                    return func.get_function_execution()
                return func
            elif scope_node.type == 'classdef':
                class_context = er.ClassContext(self, scope_node, parent_context)
                if child_is_funcdef:
                    # anonymous instance
                    return AnonymousInstance(self, parent_context, class_context)
                else:
                    return class_context
            elif scope_node.type == 'comp_for':
                if node.start_pos >= scope_node.children[-1].start_pos:
                    return parent_context
                return iterable.CompForContext.from_comp_for(parent_context, scope_node)
            raise Exception("There's a scope that was not managed.")

        base_node = base_context.tree_node

        if node_is_context and parser_utils.is_scope(node):
            scope_node = node
        else:
            if node.parent.type in ('funcdef', 'classdef') and node.parent.name == node:
                # When we're on class/function names/leafs that define the
                # object itself and not its contents.
                node = node.parent
            scope_node = parent_scope(node)
        return from_scope_node(scope_node, is_nested=True, node_is_object=node_is_object)
