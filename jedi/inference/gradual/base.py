from jedi.inference.base_value import Value
from jedi.inference.value.klass import ClassFilter
from jedi.inference.names import ValueName
from jedi.inference.compiled import builtin_from_name


class BaseTypingValue(Value):
    def __init__(self, inference_state, parent_context, tree_name):
        super(BaseTypingValue, self).__init__(inference_state, parent_context)
        self._tree_name = tree_name

    @property
    def tree_node(self):
        return self._tree_name

    def get_filters(self, *args, **kwargs):
        # TODO this is obviously wrong. Is it though?
        class EmptyFilter(ClassFilter):
            def __init__(self):
                pass

            def get(self, name, **kwargs):
                return []

            def values(self, **kwargs):
                return []

        yield EmptyFilter()

    def py__class__(self):
        # TODO this is obviously not correct, but at least gives us a class if
        # we have none. Some of these objects don't really have a base class in
        # typeshed.
        return builtin_from_name(self.inference_state, u'object')

    @property
    def name(self):
        return ValueName(self, self._tree_name)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._tree_name.value)
