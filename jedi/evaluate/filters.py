"""
Filters are objects that you can use to filter names in different scopes. They
are needed for name resolution.
"""
from abc import abstractmethod

from jedi.parser.python.tree import search_ancestor
from jedi.evaluate import flow_analysis
from jedi.common import to_list, unite


class AbstractNameDefinition(object):
    start_pos = None
    string_name = None
    parent_context = None
    tree_name = None

    @abstractmethod
    def infer(self):
        raise NotImplementedError

    def get_root_context(self):
        return self.parent_context.get_root_context()

    def __repr__(self):
        if self.start_pos is None:
            return '<%s: %s>' % (self.__class__.__name__, self.string_name)
        return '<%s: %s@%s>' % (self.__class__.__name__, self.string_name, self.start_pos)

    def execute(self, arguments):
        return unite(context.execute(arguments) for context in self.infer())

    def execute_evaluated(self, *args, **kwargs):
        return unite(context.execute_evaluated(*args, **kwargs) for context in self.infer())

    @property
    def api_type(self):
        return self.parent_context.api_type


class AbstractTreeName(AbstractNameDefinition):
    def __init__(self, parent_context, tree_name):
        self.parent_context = parent_context
        self.tree_name = tree_name

    @property
    def string_name(self):
        return self.tree_name.value

    @property
    def start_pos(self):
        return self.tree_name.start_pos


class ContextNameMixin(object):
    def infer(self):
        return set([self._context])

    def get_root_context(self):
        if self.parent_context is None:
            return self._context
        return super(ContextNameMixin, self).get_root_context()

    @property
    def api_type(self):
        return self._context.api_type


class ContextName(ContextNameMixin, AbstractTreeName):
    def __init__(self, context, tree_name):
        super(ContextName, self).__init__(context.parent_context, tree_name)
        self._context = context


class TreeNameDefinition(AbstractTreeName):
    def infer(self):
        # Refactor this, should probably be here.
        from jedi.evaluate.finder import _name_to_types
        return _name_to_types(self.parent_context.evaluator, self.parent_context, self.tree_name)

    @property
    def api_type(self):
        definition = self.tree_name.get_definition()
        return dict(
            import_name='module',
            import_from='module',
            funcdef='function',
            param='param',
            classdef='class',
        ).get(definition.type, 'statement')


class ParamName(AbstractTreeName):
    api_type = 'param'

    def __init__(self, parent_context, tree_name):
        self.parent_context = parent_context
        self.tree_name = tree_name

    def infer(self):
        return self.get_param().infer()

    def get_param(self):
        params = self.parent_context.get_params()
        param_node = search_ancestor(self.tree_name, 'param')
        return params[param_node.position_nr]


class AnonymousInstanceParamName(ParamName):
    def infer(self):
        param_node = search_ancestor(self.tree_name, 'param')
        if param_node.position_nr == 0:
            # This is a speed optimization, to return the self param (because
            # it's known). This only affects anonymous instances.
            return set([self.parent_context.instance])
        else:
            return self.get_param().infer()


class AbstractFilter(object):
    _until_position = None

    def _filter(self, names):
        if self._until_position is not None:
            return [n for n in names if n.start_pos < self._until_position]
        return names

    @abstractmethod
    def get(self, name):
        raise NotImplementedError

    @abstractmethod
    def values(self):
        raise NotImplementedError


class AbstractUsedNamesFilter(AbstractFilter):
    name_class = TreeNameDefinition

    def __init__(self, context, parser_scope):
        self._parser_scope = parser_scope
        self._used_names = self._parser_scope.get_root_node().used_names
        self.context = context

    def get(self, name):
        try:
            names = self._used_names[str(name)]
        except KeyError:
            return []

        return self._convert_names(self._filter(names))

    def _convert_names(self, names):
        return [self.name_class(self.context, name) for name in names]

    def values(self):
        return self._convert_names(name for name_list in self._used_names.values()
                                   for name in self._filter(name_list))

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.context)


class ParserTreeFilter(AbstractUsedNamesFilter):
    def __init__(self, evaluator, context, node_context=None, until_position=None,
                 origin_scope=None):
        """
        node_context is an option to specify a second context for use cases
        like the class mro where the parent class of a new name would be the
        context, but for some type inference it's important to have a local
        context of the other classes.
        """
        if node_context is None:
            node_context = context
        super(ParserTreeFilter, self).__init__(context, node_context.tree_node)
        self._node_context = node_context
        self._origin_scope = origin_scope
        self._until_position = until_position

    def _filter(self, names):
        names = super(ParserTreeFilter, self)._filter(names)
        names = [n for n in names if self._is_name_reachable(n)]
        return list(self._check_flows(names))

    def _is_name_reachable(self, name):
        if not name.is_definition():
            return False
        parent = name.parent
        if parent.type == 'trailer':
            return False
        base_node = parent if parent.type in ('classdef', 'funcdef') else name
        return base_node.get_parent_scope() == self._parser_scope

    def _check_flows(self, names):
        for name in sorted(names, key=lambda name: name.start_pos, reverse=True):
            check = flow_analysis.reachability_check(
                self._node_context, self._parser_scope, name, self._origin_scope
            )
            if check is not flow_analysis.UNREACHABLE:
                yield name

            if check is flow_analysis.REACHABLE:
                break


class FunctionExecutionFilter(ParserTreeFilter):
    param_name = ParamName

    def __init__(self, evaluator, context, node_context=None,
                 until_position=None, origin_scope=None):
        super(FunctionExecutionFilter, self).__init__(
            evaluator,
            context,
            node_context,
            until_position,
            origin_scope
        )

    @to_list
    def _convert_names(self, names):
        for name in names:
            param = search_ancestor(name, 'param')
            if param:
                yield self.param_name(self.context, name)
            else:
                yield TreeNameDefinition(self.context, name)


class AnonymousInstanceFunctionExecutionFilter(FunctionExecutionFilter):
    param_name = AnonymousInstanceParamName


class GlobalNameFilter(AbstractUsedNamesFilter):
    def __init__(self, context, parser_scope):
        super(GlobalNameFilter, self).__init__(context, parser_scope)

    @to_list
    def _filter(self, names):
        for name in names:
            if name.parent.type == 'global_stmt':
                yield name


class DictFilter(AbstractFilter):
    def __init__(self, dct):
        self._dct = dct

    def get(self, name):
        try:
            value = self._convert(name, self._dct[str(name)])
        except KeyError:
            return []

        return list(self._filter([value]))

    def values(self):
        return self._filter(self._convert(*item) for item in self._dct.items())

    def _convert(self, name, value):
        return value


def get_global_filters(evaluator, context, until_position, origin_scope):
    """
    Returns all filters in order of priority for name resolution.

    For global name lookups. The filters will handle name resolution
    themselves, but here we gather possible filters downwards.

    >>> from jedi._compatibility import u, no_unicode_pprint
    >>> from jedi import Script
    >>> script = Script(u('''
    ... x = ['a', 'b', 'c']
    ... def func():
    ...     y = None
    ... '''))
    >>> module_node = script._get_module_node()
    >>> scope = module_node.subscopes[0]
    >>> scope
    <Function: func@3-5>
    >>> context = script._get_module().create_context(scope)
    >>> filters = list(get_global_filters(context.evaluator, context, (4, 0), None))

    First we get the names names from the function scope.

    >>> no_unicode_pprint(filters[0])
    <ParserTreeFilter: <ModuleContext: @2-5>>
    >>> sorted(str(n) for n in filters[0].values())
    ['<TreeNameDefinition: func@(3, 4)>', '<TreeNameDefinition: x@(2, 0)>']
    >>> filters[0]._until_position
    (4, 0)

    Then it yields the names from one level "lower". In this example, this is
    the module scope. As a side note, you can see, that the position in the
    filter is now None, because typically the whole module is loaded before the
    function is called.

    >>> filters[1].values()  # global names -> there are none in our example.
    []
    >>> list(filters[2].values())  # package modules -> Also empty.
    []
    >>> sorted(name.string_name for name in filters[3].values())  # Module attributes
    ['__doc__', '__file__', '__name__', '__package__']
    >>> print(filters[1]._until_position)
    None

    Finally, it yields the builtin filter, if `include_builtin` is
    true (default).

    >>> filters[4].values()                              #doctest: +ELLIPSIS
    [<CompiledName: ...>, ...]
    """
    from jedi.evaluate.representation import FunctionExecutionContext
    while context is not None:
        # Names in methods cannot be resolved within the class.
        for filter in context.get_filters(
                search_global=True,
                until_position=until_position,
                origin_scope=origin_scope):
            yield filter
        if isinstance(context, FunctionExecutionContext):
            # The position should be reset if the current scope is a function.
            until_position = None

        context = context.parent_context

    # Add builtins to the global scope.
    for filter in evaluator.BUILTINS.get_filters(search_global=True):
        yield filter
