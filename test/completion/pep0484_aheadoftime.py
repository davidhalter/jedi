""" Pep-0484 type hinting with ahead of time annotations """

# python >= 3.6

somelist = [1, 2, 3, "A", "A"]
element : int
for element in somelist:
    #? int()
    element

test_string: str = NOT_DEFINED
#? str()
test_string


char: str
for char in NOT_DEFINED:
    #? str()
    char
