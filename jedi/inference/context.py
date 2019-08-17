from abc import abstractmethod

from jedi.inference.filters import ParserTreeFilter, MergedFilter, \
    GlobalNameFilter


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

    def goto(self, name_or_str, position):
        from jedi.inference import finder
        f = finder.NameFinder(self.inference_state, self, self, name_or_str, position)
        raise NotImplementedError('this does not seem to be correct')
        filters = f.get_global_filters()
        return f.filter_name(filters)

    def py__getattribute__(self, name_or_str, name_value=None, position=None,
                           analysis_errors=True):
        """
        :param position: Position of the last statement -> tuple of line, column
        """
        if name_value is None:
            name_value = self
        from jedi.inference import finder
        f = finder.NameFinder(self.inference_state, self, name_value, name_or_str,
                              position, analysis_errors=analysis_errors)
        filters = f.get_global_filters()
        return f.find(filters, attribute_lookup=False)

    @property
    def tree_node(self):
        return self._value.tree_node

    @property
    def parent_context(self):
        return self._value.parent_context

    def is_module(self):
        return self._value.is_module()

    def is_builtins_module(self):
        return self._value == self.inference_state.builtins_module

    def is_class(self):
        return self._value.is_class()

    def is_stub(self):
        return self._value.is_stub()

    def is_instance(self):
        return self._value.is_instance()

    def is_compiled(self):
        return self._value.is_compiled()

    def py__name__(self):
        return self._value.py__name__()

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

    def get_filters(self, until_position=None, origin_scope=None):
        filters = self._value.get_filters(origin_scope)
        # Skip the first filter and replace it.
        yield MergedFilter(
            ParserTreeFilter(
                context=self,
                until_position=until_position,
                origin_scope=origin_scope
            ),
            GlobalNameFilter(self, self.tree_node),
        )
        for f in filters:  # Python 2...
            yield f

    def get_value(self):
        """
        This is the only function that converts a context back to a value.
        This is necessary for stub -> python conversion and vice versa. However
        this method shouldn't be move to AbstractContext.
        """
        return self._value


class ClassContext(AbstractContext):
    def get_filters(self, until_position=None, origin_scope=None):
        yield self.get_global_filter(until_position, origin_scope)

    def get_global_filter(self, until_position=None, origin_scope=None):
        return ParserTreeFilter(
            context=self,
            until_position=until_position,
            origin_scope=origin_scope
        )
