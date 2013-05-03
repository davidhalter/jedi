# goto_assignments command tests are different in syntax

definition = 3
#! 0 ['a = definition']
a = definition

#! []
b
#! ['a = definition']
a

b = a
c = b
#! ['c = b']
c

cd = 1
#! 1 ['cd = c']
cd = c
#! 0 ['cd = e']
cd = e

#! ['module math']
import math
#! ['import math']
math

#! ['import math']
b = math
#! ['b = math']
b

class C(object):
    def b(self):
        #! ['b = math']
        b
        #! ['def b']
        self.b
        #! 14 ['def b']
        self.b()
        #! 11 ['self']
        self.b
        return 1

    #! ['def b']
    b

#! ['b = math']
b

#! ['def b']
C.b
#! ['def b']
C().b
#! 0 ['class C']
C().b
#! 0 ['class C']
C().b

D = C
#! ['def b']
D.b
#! ['def b']
D().b

#! 0 ['D = C']
D().b
#! 0 ['D = C']
D().b

def c():
    return ''

#! ['def c']
c
#! 0 ['def c']
c()

# -----------------
# imports
# -----------------

#! ['module import_tree']
import import_tree
#! ["a = ''"]
import_tree.a

#! ['module mod1']
import import_tree.mod1
#! ['a = 1']
import_tree.mod1.a

#! ['module pkg']
import import_tree.pkg
#! ['a = list']
import_tree.pkg.a

#! ['module mod1']
import import_tree.pkg.mod1
#! ['a = 1.0']
import_tree.pkg.mod1.a
#! ["a = ''"]
import_tree.a

#! ['module mod1']
from import_tree.pkg import mod1
#! ['a = 1.0']
mod1.a

#! ['module mod1']
from import_tree import mod1
#! ['a = 1']
mod1.a

#! ['a = 1.0']
from import_tree.pkg.mod1 import a

#! ['import os']
from .imports import os

#! ['some_variable = 1']
from . import some_variable

# -----------------
# anonymous classes
# -----------------
def func():
    class A():
        def b(self):
            return 1
    return A()

#! 8 ['def b']
func().b()

# -----------------
# on itself
# -----------------

#! 7 ['class ClassDef']
class ClassDef():
    """ abc """
    pass

# -----------------
# params
# -----------------

param = ClassDef
#! 8 ['param']
def ab1(param): pass
#! 9 ['param']
def ab2(param): pass
#! 11 ['param = ClassDef']
def ab3(a=param): pass

ab1(ClassDef);ab2(ClassDef);ab3(ClassDef)
