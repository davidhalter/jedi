# python >= 3.4
from typing import (
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Mapping,
    Type,
    TypeVar,
    Union,
)

K = TypeVar('K')
T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)
V = TypeVar('V')


list_of_ints = [42]  # type: List[int]
list_of_ints_and_strs = [42, 'abc']  # type: List[Union[int, str]]

# Test that simple parameters are handled
def list_t_to_list_t(the_list: List[T]) -> List[T]:
    return the_list

x0 = list_t_to_list_t(list_of_ints)[0]
#? int()
x0

for a in list_t_to_list_t(list_of_ints):
    #? int()
    a

# Test that unions are handled
x2 = list_t_to_list_t(list_of_ints_and_strs)[0]
#? int() str()
x2

for z in list_t_to_list_t(list_of_ints_and_strs):
    #? int() str()
    z


list_of_int_type = [int]  # type: List[Type[int]]

# Test that nested parameters are handled
def list_type_t_to_list_t(the_list: List[Type[T]]) -> List[T]:
    return [x() for x in the_list]


x1 = list_type_t_to_list_t(list_of_int_type)[0]
#? int()
x1


for b in list_type_t_to_list_t(list_of_int_type):
    #? int()
    b


def foo(x: T) -> T:
    return x


list_of_funcs = [foo]  # type: List[Callable[[T], T]]

def list_func_t_to_list_func_type_t(the_list: List[Callable[[T], T]]) -> List[Callable[[Type[T]], T]]:
    def adapt(func: Callable[[T], T]) -> Callable[[Type[T]], T]:
        def wrapper(typ: Type[T]) -> T:
            return func(typ())
        return wrapper
    return [adapt(x) for x in the_list]


for b in list_func_t_to_list_func_type_t(list_of_funcs):
    #? int()
    b(int)


mapping_int_str = {42: 'a'}  # type: Dict[int, str]

# Test that mappings (that have more than one parameter) are handled
def invert_mapping(mapping: Mapping[K, V]) -> Mapping[V, K]:
    return {v: k for k, v in mapping.items()}

#? int()
invert_mapping(mapping_int_str)['a']


# Test that the right type is chosen when a mapping is passed to something with
# only a single parameter. This checks that our inheritance checking picks the
# right thing.
def first(iterable: Iterable[T]) -> T:
    return next(iter(iterable))

#? int()
first(mapping_int_str)

# Test inference of str as an iterable of str.
#? str()
first("abc")

some_str = NotImplemented  # type: str
#? str()
first(some_str)


# Test that the right type is chosen when a partially realised mapping is expected
def values(mapping: Mapping[int, T]) -> List[T]:
    return list(mapping.values())

#? str()
values(mapping_int_str)[0]

x2 = values(mapping_int_str)[0]
#? str()
x2

for b in values(mapping_int_str):
    #? str()
    b


#
# Tests that user-defined generic types are handled
#
list_ints = [42]  # type: List[int]

class CustomGeneric(Generic[T_co]):
    def __init__(self, val: T_co) -> None:
        self.val = val


# Test extraction of type from a custom generic type
def custom(x: CustomGeneric[T]) -> T:
    return x.val

custom_instance = CustomGeneric(42)  # type: CustomGeneric[int]

#? int()
custom(custom_instance)

x3 = custom(custom_instance)
#? int()
x3


# Test construction of a custom generic type
def wrap_custom(iterable: Iterable[T]) -> List[CustomGeneric[T]]:
    return [CustomGeneric(x) for x in iterable]

#? int()
wrap_custom(list_ints)[0].val

x4 = wrap_custom(list_ints)[0]
#? int()
x4.val

for x5 in wrap_custom(list_ints):
    #? int()
    x5.val


# Test extraction of type from a nested custom generic type
list_custom_instances = [CustomGeneric(42)]  # type: List[CustomGeneric[int]]

def unwrap_custom(iterable: Iterable[CustomGeneric[T]]) -> List[T]:
    return [x.val for x in iterable]

#? int()
unwrap_custom(list_custom_instances)[0]

x6 = unwrap_custom(list_custom_instances)[0]
#? int()
x6

for x7 in unwrap_custom(list_custom_instances):
    #? int()
    x7


for xc in unwrap_custom([CustomGeneric(s) for s in 'abc']):
    #? str()
    xc


for xg in unwrap_custom(CustomGeneric(s) for s in 'abc'):
    #? str()
    xg


# Test extraction of type from type parameer nested within a custom generic type
custom_instance_list_int = CustomGeneric([42])  # type: CustomGeneric[List[int]]

def unwrap_custom2(instance: CustomGeneric[Iterable[T]]) -> List[T]:
    return list(instance.val)

#? int()
unwrap_custom2(custom_instance_list_int)[0]

x8 = unwrap_custom2(custom_instance_list_int)[0]
#? int()
x8

for x9 in unwrap_custom2(custom_instance_list_int):
    #? int()
    x9


# Test that classes which have generic parents but are not generic themselves
# are still inferred correctly.
class Specialised(Mapping[int, str]):
    pass


specialised_instance = NotImplemented  # type: Specialised

#? int()
first(specialised_instance)

#? str()
values(specialised_instance)[0]


# Test that classes which have generic ancestry but neither they nor their
# parents are not generic are still inferred correctly.
class ChildOfSpecialised(Specialised):
    pass


child_of_specialised_instance = NotImplemented  # type: ChildOfSpecialised

#? int()
first(child_of_specialised_instance)

#? str()
values(child_of_specialised_instance)[0]


# Test that unbound generics are inferred as much as possible
class CustomPartialGeneric1(Mapping[str, T]):
    pass


custom_partial1_instance = NotImplemented  # type: CustomPartialGeneric1[int]

#? str()
first(custom_partial1_instance)


custom_partial1_unbound_instance = NotImplemented  # type: CustomPartialGeneric1

#? str()
first(custom_partial1_unbound_instance)


class CustomPartialGeneric2(Mapping[T, str]):
    pass


custom_partial2_instance = NotImplemented  # type: CustomPartialGeneric2[int]

#? int()
first(custom_partial2_instance)

#? str()
values(custom_partial2_instance)[0]


custom_partial2_unbound_instance = NotImplemented  # type: CustomPartialGeneric2

#? []
first(custom_partial2_unbound_instance)

#? str()
values(custom_partial2_unbound_instance)[0]
