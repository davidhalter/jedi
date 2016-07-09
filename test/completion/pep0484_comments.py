a = 3  # type: str
#? str()
a

b = 3  # type: str but I write more
#? int()
b

c = 3  # type: str # I comment more
#? str()
c

d = "It should not read comments from the next line"
# type: int
#? str()
d

# type: int
e = "It should not read comments from the previous line"
#? str()
e

class BB: pass

def test(a, b):
    a = a  # type: BB
    c = a  # type: str
    d = a
    # type: str
    e = a                 # type: str           # Should ignore long whitespace

    #? BB()
    a
    #? str()
    c
    #? BB()
    d
    #? str()
    e

a,b = 1, 2 # type: str, float
#? str()
a
#? float()
b

class Employee:
    pass

# The typing library is not installable for Python 2.6, therefore ignore the
# following tests.
# python >= 2.7

from typing import List
x = []   # type: List[Employee]
#? Employee()
x[1]
x, y, z = [], [], []  # type: List[int], List[int], List[str]
#? int()
y[2]
x, y, z = [], [], []  # type: (List[float], List[float], List[BB])
for zi in z:
    #? BB()
    zi

x = [
   1,
   2,
]  # type: List[str]

#? str()
x[1]


for bar in foo():  # type: str
    #? str()
    bar

for bar, baz in foo():  # type: int, float
    #? int()
    bar
    #? float()
    baz

for bar, baz in foo():
    # type: str, str
    """ type hinting on next line should not work """
    #?
    bar
    #?
    baz

with foo():  # type: int
    ...

with foo() as f:  # type: str
    #? str()
    f

with foo() as f:
    # type: str
    """ type hinting on next line should not work """
    #?
    f

aaa = some_extremely_long_function_name_that_doesnt_leave_room_for_hints() \
    # type: float # We should be able to put hints on the next line with a \
#? float()
aaa
