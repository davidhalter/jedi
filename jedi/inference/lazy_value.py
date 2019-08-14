from jedi.inference.base_value import ContextSet, NO_CONTEXTS
from jedi.common.utils import monkeypatch


class AbstractLazyContext(object):
    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.data)

    def infer(self):
        raise NotImplementedError


class LazyKnownContext(AbstractLazyContext):
    """data is a value."""
    def infer(self):
        return ContextSet([self.data])


class LazyKnownContexts(AbstractLazyContext):
    """data is a ContextSet."""
    def infer(self):
        return self.data


class LazyUnknownContext(AbstractLazyContext):
    def __init__(self):
        super(LazyUnknownContext, self).__init__(None)

    def infer(self):
        return NO_CONTEXTS


class LazyTreeContext(AbstractLazyContext):
    def __init__(self, value, node):
        super(LazyTreeContext, self).__init__(node)
        self.value = value
        # We need to save the predefined names. It's an unfortunate side effect
        # that needs to be tracked otherwise results will be wrong.
        self._predefined_names = dict(value.predefined_names)

    def infer(self):
        with monkeypatch(self.value, 'predefined_names', self._predefined_names):
            return self.value.infer_node(self.data)


def get_merged_lazy_value(lazy_values):
    if len(lazy_values) > 1:
        return MergedLazyContexts(lazy_values)
    else:
        return lazy_values[0]


class MergedLazyContexts(AbstractLazyContext):
    """data is a list of lazy values."""
    def infer(self):
        return ContextSet.from_sets(l.infer() for l in self.data)
