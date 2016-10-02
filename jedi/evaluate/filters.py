"""
Filters are objects that you can use to filter names in different scopes. They
are needed for name resolution.
"""
from abc import abstractmethod

from jedi.parser.tree import search_ancestor


def filter_scope_names(names, scope, until_position=None, name=None):
    return names


class AbstractFilter(object):
    def _filter(self, names, until_position):
        if until_position is not None:
            return [n for n in names if n.start_pos < until_position]
        return names

    @abstractmethod
    def get(self, name, until_position=None):
        pass

    @abstractmethod
    def values(self, until_position=None):
        pass


class ParserTreeFilter(AbstractFilter):
    def __init__(self, parser_scope):
        self._parser_scope = parser_scope
        self._used_names = self._parser_scope.get_root_node().used_names

    def _filter(self, names, until_position):
        names = super(ParserTreeFilter, self)._filter(names, until_position)
        names = [n for n in names if n.is_definition()]
        names = [n for n in names if n.parent.get_parent_scope() == self._parser_scope]
        return names

    def get(self, name, until_position=None):
        try:
            names = self._used_names[str(name)]
        except KeyError:
            return []

        return self._filter(names, until_position)

    def values(self, name, until_position=None):
        return self._filter(self._used_names.values(), until_position)


class FunctionExecutionFilter(ParserTreeFilter):
    def __init__(self, parser_scope, executed_function, param_by_name):
        super(FunctionExecutionFilter, self).__init__(parser_scope)
        self._executed_function = executed_function
        self._param_by_name = param_by_name

    def _filter(self, names, until_position):
        names = super(FunctionExecutionFilter, self)._filter(names, until_position)

        names = [self._executed_function.name_for_position(name.start_pos) for name in names]
        names = [self._param_by_name(str(name)) if search_ancestor(name, 'param') else name
                 for name in names]
        return names
