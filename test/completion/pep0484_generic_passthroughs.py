# python >= 3.4
from typing import Any, Iterable, List, Tuple, TypeVar

T = TypeVar('T')
TList = TypeVar('TList', bound=List[Any])

untyped_list_str = ['abc', 'def']
typed_list_str = ['abc', 'def']  # type: List[str]

untyped_tuple_str = ('abc',)
typed_tuple_str = ('abc',)  # type: Tuple[str]


def untyped_passthrough(x):
    return x

def typed_list_generic_passthrough(x: List[T]) -> List[T]:
    return x

def typed_tuple_generic_passthrough(x: Tuple[T]) -> Tuple[T]:
    return x

def typed_iterable_generic_passthrough(x: Iterable[T]) -> Iterable[T]:
    return x

def typed_fully_generic_passthrough(x: T) -> T:
    return x

def typed_bound_generic_passthrough(x: TList) -> TList:
    return x


for a in untyped_passthrough(untyped_list_str):
    #? str()
    a

for b in untyped_passthrough(typed_list_str):
    #? str()
    b


for c in typed_list_generic_passthrough(untyped_list_str):
    #? str()
    c

for d in typed_list_generic_passthrough(typed_list_str):
    #? str()
    d


for e in typed_iterable_generic_passthrough(untyped_list_str):
    #? str()
    e

for f in typed_iterable_generic_passthrough(typed_list_str):
    #? str()
    f


for g in typed_tuple_generic_passthrough(untyped_tuple_str):
    #? str()
    g

for h in typed_tuple_generic_passthrough(typed_tuple_str):
    #? str()
    h


for n in typed_fully_generic_passthrough(untyped_list_str):
    #? str()
    n

for o in typed_fully_generic_passthrough(typed_list_str):
    #? str()
    o


for p in typed_bound_generic_passthrough(untyped_list_str):
    #? str()
    p

for q in typed_bound_generic_passthrough(typed_list_str):
    #? str()
    q
