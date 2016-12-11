"""
Searching for names with given scope and name. This is very central in Jedi and
Python. The name resolution is quite complicated with descripter,
``__getattribute__``, ``__getattr__``, ``global``, etc.

If you want to understand name resolution, please read the first few chapters
in http://blog.ionelmc.ro/2015/02/09/understanding-python-metaclasses/.

Flow checks
+++++++++++

Flow checks are not really mature. There's only a check for ``isinstance``.  It
would check whether a flow has the form of ``if isinstance(a, type_or_tuple)``.
Unfortunately every other thing is being ignored (e.g. a == '' would be easy to
check for -> a is a string). There's big potential in these checks.
"""

from jedi.parser import tree
from jedi import debug
from jedi.common import unite
from jedi import settings
from jedi.evaluate import representation as er
from jedi.evaluate.instance import AbstractInstanceContext
from jedi.evaluate import dynamic
from jedi.evaluate import compiled
from jedi.evaluate import docstrings
from jedi.evaluate import pep0484
from jedi.evaluate import iterable
from jedi.evaluate import imports
from jedi.evaluate import analysis
from jedi.evaluate import flow_analysis
from jedi.evaluate import param
from jedi.evaluate import helpers
from jedi.evaluate.filters import get_global_filters, TreeNameDefinition


def filter_after_position(names, position, origin=None):
    """
    Removes all names after a certain position. If position is None, just
    returns the names list.
    """
    if position is None:
        return names

    names_new = []
    for n in names:
        # Filter positions and also allow list comprehensions and lambdas.
        if n.start_pos[0] is not None and n.start_pos < position:
            names_new.append(n)
        elif isinstance(n.get_definition(), (tree.CompFor, tree.Lambda)):
            if origin is not None and origin.get_definition() != n.get_definition():
                # This is extremely hacky. A transition that we have to use
                # until we get rid of names_dicts.
                continue
            names_new.append(n)
    return names_new


def is_comprehension_name(name, origin):
    definition = name.get_definition()
    # TODO This is really hacky. It just compares the two definitions. This
    # fails tests and is in general just a temporary way.
    return definition.type == 'comp_for' and origin.get_definition().type != definition.type


def filter_definition_names(names, origin, position=None):
    """
    Filter names that are actual definitions in a scope. Names that are just
    used will be ignored.
    """
    if not names:
        return []

    # Just calculate the scope from the first
    stmt = names[0].get_definition()
    scope = stmt.get_parent_scope()

    if not (isinstance(scope, er.FunctionExecution) and
            isinstance(scope.base, LambdaWrapper)):
        names = filter_after_position(names, position, origin)
    names = [name for name in names
             if name.is_definition() and not is_comprehension_name(name, origin)]

    # Private name mangling (compile.c) disallows access on names
    # preceeded by two underscores `__` if used outside of the class. Names
    # that also end with two underscores (e.g. __id__) are not affected.
    for name in list(names):
        if name.value.startswith('__') and not name.value.endswith('__'):
            if filter_private_variable(scope, origin):
                names.remove(name)
    return names


class NameFinder(object):
    def __init__(self, evaluator, context, name_context, name_or_str, position=None):
        self._evaluator = evaluator
        # Make sure that it's not just a syntax tree node.
        self._context = context
        self._name_context = name_context
        self._name = name_or_str
        if isinstance(name_or_str, tree.Name):
            self._string_name = name_or_str.value
        else:
            self._string_name = name_or_str
        self._position = position
        self._found_predefined_types = None

    @debug.increase_indent
    def find(self, filters, attribute_lookup):
        """
        :params bool attribute_lookup: Tell to logic if we're accessing the
            attribute or the contents of e.g. a function.
        """
        # TODO rename scopes to names_dicts

        names = self.filter_name(filters)
        if self._found_predefined_types is not None:
            return self._found_predefined_types

        types = self._names_to_types(names, attribute_lookup)

        if not names and not types \
                and not (isinstance(self._name, tree.Name) and
                         isinstance(self._name.parent.parent, tree.Param)):
            if isinstance(self._name, tree.Name):
                if attribute_lookup:
                    analysis.add_attribute_error(self._context, self._name)
                else:
                    message = ("NameError: name '%s' is not defined."
                               % self._string_name)
                    analysis.add(self._context, 'name-error', self._name, message)

        return types

    def _get_origin_scope(self):
        if isinstance(self._name, tree.Name):
            return self._name.get_parent_until(tree.Scope, reverse=True)
        else:
            return None

    def get_filters(self, search_global=False):
        origin_scope = self._get_origin_scope()
        if search_global:
            return get_global_filters(self._evaluator, self._context, self._position, origin_scope)
        else:
            return self._context.get_filters(search_global, self._position, origin_scope=origin_scope)

    def names_dict_lookup(self, names_dict, position):
        def get_param(scope, el):
            if isinstance(el.get_parent_until(tree.Param), tree.Param):
                return scope.param_by_name(str(el))
            return el

        try:
            names = names_dict[self._string_name]
            if not names:  # We want names, otherwise stop.
                return []
        except KeyError:
            return []

        names = filter_definition_names(names, self._name, position)

        name_scope = None
        # Only the names defined in the last position are valid definitions.
        last_names = []
        for name in reversed(sorted(names, key=lambda name: name.start_pos)):
            stmt = name.get_definition()
            name_scope = self._evaluator.wrap(stmt.get_parent_scope())

            if isinstance(self._context, er.Instance) and not isinstance(name_scope, er.Instance):
                # Instances should not be checked for positioning, because we
                # don't know in which order the functions are called.
                last_names.append(name)
                continue

            if isinstance(name_scope, compiled.CompiledObject):
                # Let's test this. TODO need comment. shouldn't this be
                # filtered before?
                last_names.append(name)
                continue

            if isinstance(stmt, er.ModuleContext):
                # In case of REPL completion, we can infer modules names that
                # don't really have a definition (because they are really just
                # namespaces). In this case we can just add it.
                last_names.append(name)
                continue

            if isinstance(name, compiled.CompiledName) \
                    or isinstance(name, er.InstanceName) and isinstance(name._origin_name, compiled.CompiledName):
                last_names.append(name)
                continue

            if isinstance(self._name, tree.Name):
                origin_scope = self._name.get_parent_until(tree.Scope, reverse=True)
                scope = self._name
                check = None
                while True:
                    scope = scope.parent
                    if scope.type in ("if_stmt", "for_stmt"):
                        # TODO try removing for_stmt.
                        try:
                            name_dict = self.context.predefined_names[scope]
                            types = set(name_dict[self._string_name])
                        except KeyError:
                            continue
                        else:
                            if self._name.start_pos < scope.children[1].end_pos:
                                # It doesn't make any sense to check if
                                # statements in the if statement itself, just
                                # deliver types.
                                self._found_predefined_types = types
                            else:
                                check = flow_analysis.reachability_check(
                                    self._context, self._context, origin_scope)
                                if check is flow_analysis.UNREACHABLE:
                                    self._found_predefined_types = set()
                                else:
                                    self._found_predefined_types = types
                            break
                    if isinstance(scope, tree.IsScope) or scope is None:
                        break
            else:
                origin_scope = None

            if isinstance(stmt.parent, compiled.CompiledObject):
                # TODO seriously? this is stupid.
                continue
            check = flow_analysis.reachability_check(self._context, name_scope,
                                                     stmt, origin_scope)
            if check is not flow_analysis.UNREACHABLE:
                last_names.append(name)

            if check is flow_analysis.REACHABLE:
                break

        if isinstance(name_scope, er.FunctionExecution):
            # Replace params
            return [get_param(name_scope, n) for n in last_names]
        return last_names

    def filter_name(self, filters):
        """
        Searches names that are defined in a scope (the different
        `names_dicts`), until a name fits.
        """
        names = []
        if self._context.predefined_names:
            # TODO is this ok? node might not always be a tree.Name
            node = self._name
            while node is not None and not isinstance(node, tree.IsScope):
                node = node.parent
                if node.type in ("if_stmt", "for_stmt", "comp_for"):
                    try:
                        name_dict = self._context.predefined_names[node]
                        types = name_dict[self._string_name]
                    except KeyError:
                        continue
                    else:
                        self._found_predefined_types = types
                        return []
        for filter in filters:
            names = filter.get(self._name)
            if names:
                self._last_used_filter = filter
                break
        debug.dbg('finder.filter_name "%s" in (%s): %s@%s', self._string_name,
                  self._context, names, self._position)
        return list(self._clean_names(names))

    def _clean_names(self, names):
        """
        ``NameFinder.filter_name`` should only output names with correct
        wrapper parents. We don't want to see AST classes out in the
        evaluation, so remove them already here!
        """

        return names
        #for n in names:
        #    definition = n.parent
        #    if isinstance(definition, (compiled.CompiledObject,
        #        iterable.BuiltinMethod)):
        #        # TODO this if should really be removed by changing the type of
        #        #      those classes.
        #        yield n
        #    elif definition.type in ('funcdef', 'classdef', 'file_input'):
        #        yield self._evaluator.wrap(definition).name
        #    else:
        #        yield n

    def _check_getattr(self, inst):
        """Checks for both __getattr__ and __getattribute__ methods"""
        # str is important, because it shouldn't be `Name`!
        name = compiled.create(self._evaluator, self._string_name)

        # This is a little bit special. `__getattribute__` is in Python
        # executed before `__getattr__`. But: I know no use case, where
        # this could be practical and where Jedi would return wrong types.
        # If you ever find something, let me know!
        # We are inversing this, because a hand-crafted `__getattribute__`
        # could still call another hand-crafted `__getattr__`, but not the
        # other way around.
        names = (inst.get_function_slot_names('__getattr__') or
                 inst.get_function_slot_names('__getattribute__'))
        return inst.execute_function_slots(names, name)

    def _names_to_types(self, names, attribute_lookup):
        types = set()

        types = unite(name.infer() for name in names)

        debug.dbg('finder._names_to_types: %s -> %s', names, types)
        if not names and isinstance(self._context, AbstractInstanceContext):
            # handling __getattr__ / __getattribute__
            return self._check_getattr(self._context)

        # Add isinstance and other if/assert knowledge.
        if not types and isinstance(self._name, tree.Name) and \
                not isinstance(self._name_context, AbstractInstanceContext):
            flow_scope = self._name
            base_node = self._name_context.get_node()
            if base_node.type == 'comp_for':
                return types
            while True:
                flow_scope = flow_scope.get_parent_scope(include_flows=True)
                n = _check_flow_information(self._name_context, flow_scope,
                                            self._name, self._position)
                if n is not None:
                    return n
                if flow_scope == base_node:
                    break
        return types


def _name_to_types(evaluator, context, name):
    types = []
    node = name.get_definition()
    if node.isinstance(tree.ForStmt):
        types = pep0484.find_type_from_comment_hint_for(context, node, name)
        if types:
            return types
    if node.isinstance(tree.WithStmt):
        types = pep0484.find_type_from_comment_hint_with(context, node, name)
        if types:
            return types
    if node.type in ('for_stmt', 'comp_for'):
        try:
            types = context.predefined_names[node][name.value]
        except KeyError:
            container_types = context.eval_node(node.children[3])
            for_types = iterable.py__iter__types(evaluator, container_types, node.children[3])
            types = check_tuple_assignments(evaluator, for_types, name)
    elif isinstance(node, tree.Param):
        return set()  # TODO remove
        types = _eval_param(evaluator, context, node)
    elif node.isinstance(tree.ExprStmt):
        types = _remove_statements(evaluator, context, node, name)
    elif node.isinstance(tree.WithStmt):
        types = context.eval_node(node.node_from_name(name))
    elif isinstance(node, tree.Import):
        types = imports.ImportWrapper(context, name).follow()
    elif node.type in ('funcdef', 'classdef'):
        types = _apply_decorators(evaluator, context, node)
    elif node.type == 'global_stmt':
        context = evaluator.create_context(context, name)
        finder = NameFinder(evaluator, context, context, str(name))
        filters = finder.get_filters(search_global=True)
        # For global_stmt lookups, we only need the first possible scope,
        # which means the function itself.
        filters = [next(filters)]
        types += finder.find(filters, attribute_lookup=False)
    elif isinstance(node, tree.TryStmt):
        # TODO an exception can also be a tuple. Check for those.
        # TODO check for types that are not classes and add it to
        # the static analysis report.
        exceptions = context.eval_node(name.get_previous_sibling().get_previous_sibling())
        types = unite(
            evaluator.execute(t, param.ValuesArguments([]))
            for t in exceptions
        )
    else:
        raise DeprecationWarning
        types = set([node])
    return types


def _apply_decorators(evaluator, context, node):
    """
    Returns the function, that should to be executed in the end.
    This is also the places where the decorators are processed.
    """
    if node.type == 'classdef':
        decoratee_context = er.ClassContext(
            evaluator,
            parent_context=context,
            classdef=node
        )
    else:
        decoratee_context = er.FunctionContext(
            evaluator,
            parent_context=context,
            funcdef=node
        )
    initial = values = set([decoratee_context])
    for dec in reversed(node.get_decorators()):
        debug.dbg('decorator: %s %s', dec, values)
        dec_values = context.eval_node(dec.children[1])
        trailer_nodes = dec.children[2:-1]
        if trailer_nodes:
            # Create a trailer and evaluate it.
            trailer = tree.Node('trailer', trailer_nodes)
            trailer.parent = dec
            dec_values = evaluator.eval_trailer(context, dec_values, trailer)

        if not len(dec_values):
            debug.warning('decorator not found: %s on %s', dec, node)
            return initial

        values = unite(dec_value.execute(param.ValuesArguments([values]))
                       for dec_value in dec_values)
        if not len(values):
            debug.warning('not possible to resolve wrappers found %s', node)
            return initial

        debug.dbg('decorator end %s', values)
    return values


def _remove_statements(evaluator, context, stmt, name):
    """
    This is the part where statements are being stripped.

    Due to lazy evaluation, statements like a = func; b = a; b() have to be
    evaluated.
    """
    types = set()
    # Remove the statement docstr stuff for now, that has to be
    # implemented with the evaluator class.
    #if stmt.docstr:
        #res_new.append(stmt)

    check_instance = None

    pep0484types = \
        pep0484.find_type_from_comment_hint_assign(context, stmt, name)
    if pep0484types:
        return pep0484types
    types |= context.eval_stmt(stmt, seek_name=name)

    if check_instance is not None:
        # class renames
        types = set([er.get_instance_el(evaluator, check_instance, a, True)
                     if isinstance(a, (er.Function, tree.Function))
                     else a for a in types])
    return types


def _eval_param(evaluator, context, param, scope):
    res_new = set()
    func = param.get_parent_scope()

    cls = func.parent.get_parent_until((tree.Class, tree.Function))

    from jedi.evaluate.param import ExecutedParam, Arguments
    if isinstance(cls, tree.Class) and param.position_nr == 0 \
            and not isinstance(param, ExecutedParam):
        # This is where we add self - if it has never been
        # instantiated.
        if isinstance(scope, er.InstanceElement):
            res_new.add(scope.instance)
        else:
            inst = er.Instance(evaluator, context.parent_context.parent_context, context.parent_context,
                               Arguments(evaluator, context),
                               is_generated=True)
            res_new.add(inst)
        return res_new

    # Instances are typically faked, if the instance is not called from
    # outside. Here we check it for __init__ functions and return.
    if isinstance(func, er.InstanceElement) \
            and func.instance.is_generated and str(func.name) == '__init__':
        param = func.var.params[param.position_nr]

    # Add pep0484 and docstring knowledge.
    pep0484_hints = pep0484.follow_param(evaluator, param)
    doc_params = docstrings.follow_param(evaluator, param)
    if pep0484_hints or doc_params:
        return list(set(pep0484_hints) | set(doc_params))

    if isinstance(param, ExecutedParam):
        return res_new | param.eval(evaluator)
    else:
        # Param owns no information itself.
        res_new |= dynamic.search_params(evaluator, param)
        if not res_new:
            if param.stars:
                t = 'tuple' if param.stars == 1 else 'dict'
                typ = list(evaluator.BUILTINS.py__getattribute__(t))[0]
                res_new = evaluator.execute(typ)
        if param.default:
            res_new |= evaluator.eval_element(context, param.default)
        return res_new


def _check_flow_information(context, flow, search_name, pos):
    """ Try to find out the type of a variable just with the information that
    is given by the flows: e.g. It is also responsible for assert checks.::

        if isinstance(k, str):
            k.  # <- completion here

    ensures that `k` is a string.
    """
    if not settings.dynamic_flow_information:
        return None

    result = None
    if flow.is_scope():
        # Check for asserts.
        module_node = flow.get_root_node()
        try:
            names = module_node.used_names[search_name.value]
        except KeyError:
            return None
        names = reversed([
            n for n in names
            if flow.start_pos <= n.start_pos < (pos or flow.end_pos)
        ])

        for name in names:
            ass = tree.search_ancestor(name, 'assert_stmt')
            if ass is not None:
                result = _check_isinstance_type(context, ass.assertion(), search_name)
                if result is not None:
                    return result

    if isinstance(flow, (tree.IfStmt, tree.WhileStmt)):
        potential_ifs = [c for c in flow.children[1::4] if c != ':']
        for if_test in reversed(potential_ifs):
            if search_name.start_pos > if_test.end_pos:
                return _check_isinstance_type(context, if_test, search_name)
    return result


def _check_isinstance_type(context, element, search_name):
    try:
        assert element.type in ('power', 'atom_expr')
        # this might be removed if we analyze and, etc
        assert len(element.children) == 2
        first, trailer = element.children
        assert isinstance(first, tree.Name) and first.value == 'isinstance'
        assert trailer.type == 'trailer' and trailer.children[0] == '('
        assert len(trailer.children) == 3

        # arglist stuff
        arglist = trailer.children[1]
        args = param.TreeArguments(context.evaluator, context, arglist, trailer)
        param_list = list(args.unpack())
        # Disallow keyword arguments
        assert len(param_list) == 2
        (key1, lazy_context_object), (key2, lazy_context_cls) = param_list
        assert key1 is None and key2 is None
        call = helpers.call_of_leaf(search_name)
        is_instance_call = helpers.call_of_leaf(lazy_context_object.data)
        # Do a simple get_code comparison. They should just have the same code,
        # and everything will be all right.
        assert is_instance_call.get_code(normalized=True) == call.get_code(normalized=True)
    except AssertionError:
        return None

    result = set()
    for cls_or_tup in lazy_context_cls.infer():
        if isinstance(cls_or_tup, iterable.AbstractSequence) and \
                cls_or_tup.array_type == 'tuple':
            for lazy_context in cls_or_tup.py__iter__():
                for context in lazy_context.infer():
                    result |= context.execute_evaluated()
        else:
            result |= cls_or_tup.execute_evaluated()
    return result


def global_names_dict_generator(evaluator, scope, position):
    """
    For global name lookups. Yields tuples of (names_dict, position). If the
    position is None, the position does not matter anymore in that scope.

    This function is used to include names from outer scopes. For example, when
    the current scope is function:

    >>> from jedi._compatibility import u, no_unicode_pprint
    >>> from jedi.parser import ParserWithRecovery, load_grammar
    >>> parser = ParserWithRecovery(load_grammar(), u('''
    ... x = ['a', 'b', 'c']
    ... def func():
    ...     y = None
    ... '''))
    >>> scope = parser.module.subscopes[0]
    >>> scope
    <Function: func@3-5>

    `global_names_dict_generator` is a generator.  First it yields names from
    most inner scope.

    >>> from jedi.evaluate import Evaluator
    >>> evaluator = Evaluator(load_grammar())
    >>> scope = evaluator.wrap(scope)
    >>> pairs = list(global_names_dict_generator(evaluator, scope, (4, 0)))
    >>> no_unicode_pprint(pairs[0])
    ({'func': [], 'y': [<Name: y@4,4>]}, (4, 0))

    Then it yields the names from one level "lower". In this example, this
    is the most outer scope. As you can see, the position in the tuple is now
    None, because typically the whole module is loaded before the function is
    called.

    >>> no_unicode_pprint(pairs[1])
    ({'func': [<Name: func@3,4>], 'x': [<Name: x@2,0>]}, None)

    After that we have a few underscore names that are part of the module.

    >>> sorted(pairs[2][0].keys())
    ['__doc__', '__file__', '__name__', '__package__']
    >>> pairs[3]  # global names -> there are none in our example.
    ({}, None)
    >>> pairs[4]  # package modules -> Also none.
    ({}, None)

    Finally, it yields names from builtin, if `include_builtin` is
    true (default).

    >>> pairs[5][0].values()                              #doctest: +ELLIPSIS
    [[<CompiledName: ...>], ...]
    """
    in_func = False
    while scope is not None:
        if not (scope.type == 'classdef' and in_func):
            # Names in methods cannot be resolved within the class.

            for names_dict in scope.names_dicts(True):
                yield names_dict, position
                if hasattr(scope, 'resets_positions'):
                    # TODO This is so ugly, seriously. However there's
                    #      currently no good way of influencing
                    #      global_names_dict_generator when it comes to certain
                    #      objects.
                    position = None
            if scope.type == 'funcdef':
                # The position should be reset if the current scope is a function.
                in_func = True
                position = None
        scope = evaluator.wrap(scope.get_parent_scope())

    # Add builtins to the global scope.
    for names_dict in evaluator.BUILTINS.names_dicts(True):
        yield names_dict, None


def check_tuple_assignments(evaluator, types, name):
    """
    Checks if tuples are assigned.
    """
    lazy_context = None
    for index, node in name.assignment_indexes():
        iterated = iterable.py__iter__(evaluator, types, node)
        for _ in range(index + 1):
            try:
                lazy_context = next(iterated)
            except StopIteration:
                # We could do this with the default param in next. But this
                # would allow this loop to run for a very long time if the
                # index number is high. Therefore break if the loop is
                # finished.
                return set()
        types = lazy_context.infer()
    return types


def filter_private_variable(scope, origin_node):
    """Check if a variable is defined inside the same class or outside."""
    instance = scope.get_parent_scope()
    coming_from = origin_node
    while coming_from is not None \
            and not isinstance(coming_from, (tree.Class, compiled.CompiledObject)):
        coming_from = coming_from.get_parent_scope()

    # CompiledObjects don't have double underscore attributes, but Jedi abuses
    # those for fakes (builtins.pym -> list).
    if isinstance(instance, compiled.CompiledObject):
        return instance != coming_from
    else:
        return isinstance(instance, er.Instance) and instance.base.base != coming_from
