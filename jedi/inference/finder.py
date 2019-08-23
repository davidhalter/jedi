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

from parso.python import tree
from parso.tree import search_ancestor
from jedi import debug
from jedi import settings
from jedi.inference import compiled
from jedi.inference import analysis
from jedi.inference import flow_analysis
from jedi.inference.arguments import TreeArguments
from jedi.inference import helpers
from jedi.inference.value import iterable
from jedi.inference.names import TreeNameDefinition
from jedi.inference.base_value import ValueSet, NO_VALUES
from jedi.parser_utils import is_scope, get_parent_scope


class NameFinder(object):
    def __init__(self, inference_state, context, name_value, name_or_str,
                 position=None, analysis_errors=True):
        self._inference_state = inference_state
        # Make sure that it's not just a syntax tree node.
        self._context = context
        self._name_context = name_value
        self._name = name_or_str
        if isinstance(name_or_str, tree.Name):
            self._string_name = name_or_str.value
        else:
            self._string_name = name_or_str
        self._position = position
        self._found_predefined_types = None
        self._analysis_errors = analysis_errors

    def find(self, filters, attribute_lookup):
        """
        :params bool attribute_lookup: Tell to logic if we're accessing the
            attribute or the contents of e.g. a function.
        """
        names = self.filter_name(filters)
        if self._found_predefined_types is not None and names:
            check = flow_analysis.reachability_check(
                context=self._context,
                value_scope=self._context.tree_node,
                node=self._name,
            )
            if check is flow_analysis.UNREACHABLE:
                return NO_VALUES
            return self._found_predefined_types

        types = self._names_to_types(names)

        if not names and self._analysis_errors and not types \
                and not (isinstance(self._name, tree.Name) and
                         isinstance(self._name.parent.parent, tree.Param)):
            if isinstance(self._name, tree.Name):
                if attribute_lookup:
                    analysis.add_attribute_error(
                        self._name_context, self._context, self._name)
                else:
                    message = ("NameError: name '%s' is not defined."
                               % self._string_name)
                    analysis.add(self._name_context, 'name-error', self._name, message)

        return types

    def filter_name(self, filters):
        """
        Searches names that are defined in a scope (the different
        ``filters``), until a name fits.
        """
        names = []
        # This paragraph is currently needed for proper branch type inference
        # (static analysis).
        if self._context.predefined_names and isinstance(self._name, tree.Name):
            node = self._name
            while node is not None and not is_scope(node):
                node = node.parent
                if node.type in ("if_stmt", "for_stmt", "comp_for", 'sync_comp_for'):
                    try:
                        name_dict = self._context.predefined_names[node]
                        types = name_dict[self._string_name]
                    except KeyError:
                        continue
                    else:
                        self._found_predefined_types = types
                        break

        for filter in filters:
            names = filter.get(self._string_name)
            if names:
                if len(names) == 1:
                    n, = names
                    if isinstance(n, TreeNameDefinition):
                        # Something somewhere went terribly wrong. This
                        # typically happens when using goto on an import in an
                        # __init__ file. I think we need a better solution, but
                        # it's kind of hard, because for Jedi it's not clear
                        # that that name has not been defined, yet.
                        if n.tree_name == self._name:
                            def_ = self._name.get_definition()
                            if def_ is not None and def_.type == 'import_from':
                                continue
                break

        debug.dbg('finder.filter_name %s in (%s): %s@%s',
                  self._string_name, self._context, names, self._position)
        return list(names)

    def _names_to_types(self, names):
        values = ValueSet.from_sets(name.infer() for name in names)

        debug.dbg('finder._names_to_types: %s -> %s', names, values)
        # Add isinstance and other if/assert knowledge.
        if not values and isinstance(self._name, tree.Name) and \
                not self._name_context.is_instance() and not self._context.is_compiled():
            flow_scope = self._name
            base_nodes = [self._name_context.tree_node]

            if any(b.type in ('comp_for', 'sync_comp_for') for b in base_nodes):
                return values
            while True:
                flow_scope = get_parent_scope(flow_scope, include_flows=True)
                n = _check_flow_information(self._name_context, flow_scope,
                                            self._name, self._position)
                if n is not None:
                    return n
                if flow_scope in base_nodes:
                    break
        return values


def _check_flow_information(value, flow, search_name, pos):
    """ Try to find out the type of a variable just with the information that
    is given by the flows: e.g. It is also responsible for assert checks.::

        if isinstance(k, str):
            k.  # <- completion here

    ensures that `k` is a string.
    """
    if not settings.dynamic_flow_information:
        return None

    result = None
    if is_scope(flow):
        # Check for asserts.
        module_node = flow.get_root_node()
        try:
            names = module_node.get_used_names()[search_name.value]
        except KeyError:
            return None
        names = reversed([
            n for n in names
            if flow.start_pos <= n.start_pos < (pos or flow.end_pos)
        ])

        for name in names:
            ass = search_ancestor(name, 'assert_stmt')
            if ass is not None:
                result = _check_isinstance_type(value, ass.assertion, search_name)
                if result is not None:
                    return result

    if flow.type in ('if_stmt', 'while_stmt'):
        potential_ifs = [c for c in flow.children[1::4] if c != ':']
        for if_test in reversed(potential_ifs):
            if search_name.start_pos > if_test.end_pos:
                return _check_isinstance_type(value, if_test, search_name)
    return result


def _check_isinstance_type(value, element, search_name):
    try:
        assert element.type in ('power', 'atom_expr')
        # this might be removed if we analyze and, etc
        assert len(element.children) == 2
        first, trailer = element.children
        assert first.type == 'name' and first.value == 'isinstance'
        assert trailer.type == 'trailer' and trailer.children[0] == '('
        assert len(trailer.children) == 3

        # arglist stuff
        arglist = trailer.children[1]
        args = TreeArguments(value.inference_state, value, arglist, trailer)
        param_list = list(args.unpack())
        # Disallow keyword arguments
        assert len(param_list) == 2
        (key1, lazy_value_object), (key2, lazy_value_cls) = param_list
        assert key1 is None and key2 is None
        call = helpers.call_of_leaf(search_name)
        is_instance_call = helpers.call_of_leaf(lazy_value_object.data)
        # Do a simple get_code comparison. They should just have the same code,
        # and everything will be all right.
        normalize = value.inference_state.grammar._normalize
        assert normalize(is_instance_call) == normalize(call)
    except AssertionError:
        return None

    value_set = NO_VALUES
    for cls_or_tup in lazy_value_cls.infer():
        if isinstance(cls_or_tup, iterable.Sequence) and cls_or_tup.array_type == 'tuple':
            for lazy_value in cls_or_tup.py__iter__():
                value_set |= lazy_value.infer().execute_with_values()
        else:
            value_set |= cls_or_tup.execute_with_values()
    return value_set
