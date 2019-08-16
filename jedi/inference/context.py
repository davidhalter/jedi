from abc import abstractmethod

from jedi.inference.filters import ParserTreeFilter


class AbstractContext(object):
    """
    Should be defined, otherwise the API returns empty types.
    """
    predefined_names = {}

    def __init__(self, value):
        self.inference_state = value.inference_state
        self._value = value

    @abstractmethod
    def get_filters(self, until_position=None, origin_scope=None):
        raise NotImplementedError

    def get_root_context(self):
        return self._value.get_root_context()

    def create_context(self, node, node_is_value=False, node_is_object=False):
        return self.inference_state.create_context(self, node, node_is_value, node_is_object)

    @property
    def py__getattribute__(self):
        return self._value.py__getattribute__

    @property
    def tree_node(self):
        return self._value.tree_node

    def infer_node(self, node):
        return self.inference_state.infer_element(self, node)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._value)


class FunctionContext(AbstractContext):
    def get_filters(self, until_position=None, origin_scope=None):
        yield ParserTreeFilter(
            self.inference_state,
            context=self,
            until_position=until_position,
            origin_scope=origin_scope
        )


class ModuleContext(AbstractContext):
    def py__file__(self):
        return self._value.py__file__()

    @property
    def py__package__(self):
        return self._value.py__package__


class ClassContext(AbstractContext):
    def get_filters(self, until_position=None, origin_scope=None):
        yield self._value.get_global_filter(until_position, origin_scope)

    def get_global_filter(self, until_position=None, origin_scope=None):
        return ParserTreeFilter(
            value=self,
            until_position=until_position,
            origin_scope=origin_scope
        )
