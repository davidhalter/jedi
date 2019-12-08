from jedi.inference.base_value import ValueSet, Value, \
    iterator_to_value_set, LazyValueWrapper, ValueWrapper
from jedi.inference.value.iterable import SequenceLiteralValue
from jedi.inference.helpers import is_string


def iter_over_arguments(maybe_tuple_value, defining_context):
    def iterate():
        if isinstance(maybe_tuple_value, SequenceLiteralValue):
            for lazy_value in maybe_tuple_value.py__iter__(contextualized_node=None):
                yield lazy_value.infer()
        else:
            yield ValueSet([maybe_tuple_value])

    def resolve_forward_references(value_set):
        for value in value_set:
            if is_string(value):
                from jedi.inference.gradual.annotation import _get_forward_reference_node
                node = _get_forward_reference_node(defining_context, value.get_safe_value())
                if node is not None:
                    for c in defining_context.infer_node(node):
                        yield c
            else:
                yield value

    for value_set in iterate():
        yield ValueSet(resolve_forward_references(value_set))
