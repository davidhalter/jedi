# python >= 3.4
from typing import Iterable, List, Type, TypeVar, Dict, Mapping, Generic

K = TypeVar('K')
T = TypeVar('T')
T_co = TypeVar('T_co', covariant=True)
V = TypeVar('V')


list_of_ints = [42]  # type: List[int]

# Test that simple parameters are handled
def list_t_to_list_t(the_list: List[T]) -> List[T]:
    return the_list

x0 = list_t_to_list_t(list_of_ints)[0]
#? int()
x0

for a in list_t_to_list_t(list_of_ints):
    #? int()
    a


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
