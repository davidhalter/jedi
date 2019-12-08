from jedi.cache import memoize_method
from jedi.inference.utils import to_list
from jedi.inference.base_value import ValueSet
from jedi.inference.value.iterable import SequenceLiteralValue
from jedi.inference.helpers import is_string


def iter_over_arguments(maybe_tuple_value, defining_context):
    def iterate():
        if isinstance(maybe_tuple_value, SequenceLiteralValue):
            for lazy_value in maybe_tuple_value.py__iter__(contextualized_node=None):
                yield lazy_value.infer()
        else:
            yield ValueSet([maybe_tuple_value])

    for value_set in iterate():
        yield ValueSet(_resolve_forward_references(defining_context, value_set))


def _resolve_forward_references(context, value_set):
    for value in value_set:
        if is_string(value):
            from jedi.inference.gradual.annotation import _get_forward_reference_node
            node = _get_forward_reference_node(context, value.get_safe_value())
            if node is not None:
                for c in context.infer_node(node):
                    yield c
        else:
            yield value


class LazyGenericManager(object):
    def __init__(self, context_of_index, index_value):
        self._context_of_index = context_of_index
        self._index_value = index_value

    @memoize_method
    def __getitem__(self, index):
        return self._list()[index]()

    def __len__(self):
        return len(self._list())

    @memoize_method
    @to_list
    def _list(self):
        if isinstance(self._index_value, SequenceLiteralValue):
            for lazy_value in self._index_value.py__iter__(contextualized_node=None):
                yield lambda: _resolve_forward_references(
                    self._context_of_index,
                    lazy_value.infer()
                )
        else:
            yield lambda: ValueSet([
                _resolve_forward_references(self._context_of_index, self._index_value)
            ])

    def __iter__(self):
        return iter(self._iterate())


class ListGenericManager(object):
    def __init__(self, lst):
        self._lst = lst

    def __getitem__(self, index):
        return self._lst[index]

    def __len__(self):
        return len(self._lst)

    def __iter__(self):
        for value_set in self._lst:
            yield lambda: value_set
