"""
Filters are objects that you can use to filter names in different scopes. They
are needed for name resolution.
"""
from abc import abstractmethod

from jedi.parser.tree import search_ancestor
from jedi.evaluate import flow_analysis
from jedi.common import to_list


class AbstractFilter(object):
    _until_position = None

    def __init__(self, origin_scope=None):
        self._origin_scope = origin_scope

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
    def __init__(self, parser_scope, origin_scope=None):
        super(AbstractUsedNamesFilter, self).__init__(origin_scope)
        self._parser_scope = parser_scope
        self._used_names = self._parser_scope.get_root_node().used_names

    def get(self, name):
        try:
            names = self._used_names[str(name)]
        except KeyError:
            return []

        return list(self._filter(names))

    def values(self):
        return self._filter(self._used_names.values())


class ParserTreeFilter(AbstractUsedNamesFilter):
    def __init__(self, evaluator, parser_scope, until_position=None, origin_scope=None):
        super(ParserTreeFilter, self).__init__(parser_scope, origin_scope)
        self._until_position = until_position
        self._evaluator = evaluator

    def _filter(self, names):
        names = super(ParserTreeFilter, self)._filter(names)
        names = [n for n in names if n.is_definition()]
        names = [n for n in names if n.parent.get_parent_scope() == self._parser_scope]

        return list(self._check_flows(names))

    def _check_flows(self, names):
        for name in sorted(names, key=lambda name: name.start_pos, reverse=True):
            stmt = name.get_definition()
            name_scope = self._evaluator.wrap(stmt.get_parent_scope())
            check = flow_analysis.break_check(self._evaluator, name_scope,
                                              stmt, self._origin_scope)
            if check is not flow_analysis.UNREACHABLE:
                yield name

            if check is flow_analysis.REACHABLE:
                break


class FunctionExecutionFilter(ParserTreeFilter):
    def __init__(self, evaluator, parser_scope, executed_function, param_by_name,
                 until_position=None, origin_scope=None):
        super(FunctionExecutionFilter, self).__init__(
            evaluator,
            parser_scope,
            until_position,
            origin_scope
        )
        self._executed_function = executed_function
        self._param_by_name = param_by_name

    def _filter(self, names):
        names = super(FunctionExecutionFilter, self)._filter(names)

        names = [self._executed_function.name_for_position(name.start_pos) for name in names]
        names = [self._param_by_name(str(name)) if search_ancestor(name, 'param') else name
                 for name in names]
        return names


class GlobalNameFilter(AbstractUsedNamesFilter):
    def __init__(self, parser_scope, origin_scope=None):
        super(GlobalNameFilter, self).__init__(parser_scope)

    @to_list
    def _filter(self, names):
        for name in names:
            if name.parent.type == 'global_stmt':
                yield name


def get_global_filters(evaluator, context, until_position):
    """
    Returns all filters in order of priority for name resolution.
    """
    while context is not None:
        for filter in context.get_filters(search_global=True, until_position=until_position):
            yield filter
        if context.type == 'funcdef':
            until_position = None

        node = context.get_parent_scope()
        context = evaluator.wrap(node)

    # Add builtins to the global scope.
    for filter in evaluator.BUILTINS.get_filters(search_global=True):
        yield filter
