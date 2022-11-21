"""
PEP 526 introduced a way of using type annotations on variables.
"""
import typing

asdf = ''
asdf: int
# This is not necessarily correct, but for now this is ok (at least no error).
#? int()
asdf


direct: int = NOT_DEFINED
#? int()
direct

with_typing_module: typing.List[float] = NOT_DEFINED
#? float()
with_typing_module[0]

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


# -------------------------
# instance/class vars
# -------------------------

class Foo():
    bar: int
    baz: typing.ClassVar[str]


#? int()
Foo.bar
#? int()
Foo().bar
#? str()
Foo.baz
#? str()
Foo().baz

class VarClass:
    var_instance1: int = ''
    var_instance2: float
    var_class1: typing.ClassVar[str] = 1
    var_class2: typing.ClassVar[bytes]
    var_class3 = None

    def __init__(self):
        #? int()
        d.var_instance1
        #? float()
        d.var_instance2
        #? str()
        d.var_class1
        #? bytes()
        d.var_class2
        #? []
        d.int
        #? ['var_class1', 'var_class2', 'var_instance1', 'var_instance2', 'var_class3']
        self.var_

class VarClass2(VarClass):
    var_class3: typing.ClassVar[int]

    def __init__(self):
        #? int()
        self.var_class3

#? ['var_class1', 'var_class2', 'var_instance1', 'var_class3', 'var_instance2']
VarClass.var_
#? int()
VarClass.var_instance1
#? float()
VarClass.var_instance2
#? str()
VarClass.var_class1
#? bytes()
VarClass.var_class2
#? []
VarClass.int

d = VarClass()
#? ['var_class1', 'var_class2', 'var_class3', 'var_instance1', 'var_instance2']
d.var_
#? int()
d.var_instance1
#? float()
d.var_instance2
#? str()
d.var_class1
#? bytes()
d.var_class2
#? []
d.int



import dataclasses
@dataclasses.dataclass
class DC:
    name: int = 1

#? int()
DC().name
