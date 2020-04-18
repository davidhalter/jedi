# python >= 3.4
from typing import Any, Iterable, List, Sequence, Tuple, TypeVar, Union

T = TypeVar('T')
U = TypeVar('U')
TList = TypeVar('TList', bound=List[Any])

untyped_list_str = ['abc', 'def']
typed_list_str = ['abc', 'def']  # type: List[str]

untyped_tuple_str = ('abc',)
typed_tuple_str = ('abc',)  # type: Tuple[str]

untyped_tuple_str_int = ('abc', 4)
typed_tuple_str_int = ('abc', 4)  # type: Tuple[str, int]

variadic_tuple_str = ('abc',)  # type: Tuple[str, ...]
variadic_tuple_str_int = ('abc', 4)  # type: Tuple[Union[str, int], ...]


def untyped_passthrough(x):
    return x

def typed_list_generic_passthrough(x: List[T]) -> List[T]:
    return x

def typed_tuple_generic_passthrough(x: Tuple[T]) -> Tuple[T]:
    return x

def typed_multi_typed_tuple_generic_passthrough(x: Tuple[T, U]) -> Tuple[U, T]:
    return x[1], x[0]

def typed_variadic_tuple_generic_passthrough(x: Tuple[T, ...]) -> Sequence[T]:
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


out_untyped = typed_multi_typed_tuple_generic_passthrough(untyped_tuple_str_int)
#? int()
out_untyped[0]
#? str()
out_untyped[1]


out_typed = typed_multi_typed_tuple_generic_passthrough(typed_tuple_str_int)
#? int()
out_typed[0]
#? str()
out_typed[1]


for j in typed_variadic_tuple_generic_passthrough(untyped_tuple_str_int):
    #? str() int()
    j

for k in typed_variadic_tuple_generic_passthrough(typed_tuple_str_int):
    #? str() int()
    k

for l in typed_variadic_tuple_generic_passthrough(variadic_tuple_str):
    #? str()
    l

for m in typed_variadic_tuple_generic_passthrough(variadic_tuple_str_int):
    #? str() int()
    m


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
