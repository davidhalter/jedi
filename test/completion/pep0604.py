from pep0484_generic_parameters import list_t_to_list_t

list_of_ints_and_strs: list[int | str]

# Test that unions are handled
x2 = list_t_to_list_t(list_of_ints_and_strs)[0]
#? int() str()
x2

for z in list_t_to_list_t(list_of_ints_and_strs):
    #? int() str()
    z


from pep0484_generic_passthroughs import (
    typed_variadic_tuple_generic_passthrough,
)

variadic_tuple_str_int: tuple[int | str, ...]

for m in typed_variadic_tuple_generic_passthrough(variadic_tuple_str_int):
    #? str() int()
    m


def func_returns_byteslike() -> bytes | bytearray:
    pass

#? bytes() bytearray()
func_returns_byteslike()


pep604_optional_1: int | str | None
pep604_optional_2: None | bytes

#? int() str() None
pep604_optional_1

#? None bytes()
pep604_optional_2


pep604_in_str: "int | bytes"

#? int() bytes()
pep604_in_str
