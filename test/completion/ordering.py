# -----------------
# normal
# -----------------
a = ""
a = 1

#? ['real']
a.real
#? []
a.upper
#? []
a.append

a = list

b = 1; b = ""
#? ['upper']
b.upper
#? []
b.real

a = 1
temp = b;
b = a
a = temp
#? ['real']
b.real
#? []
b.upper
#? []
a.real
#? ['upper']
a.upper

a = tuple
if 1:
    a = list

#? ['append']
a.append
#? ['index']
a.index

# -----------------
# tuples exchanges
# -----------------
a, b = 1, ""
#? ['real']
a.real
#? []
a.upper
#? []
b.real
#? ['upper']
b.upper

b, a = a, b
#? ['real']
b.real
#? []
b.upper
#? []
a.real
#? ['upper']
a.upper

b, a = a, b
#? ['real']
a.real
#? []
a.upper
#? []
b.real
#? ['upper']
b.upper

# -----------------
# function stuff
# -----------------
def a(a=3):
    #? ['real']
    a.real
    #? []
    a.upper
    #? []
    a.func
    return a

#? ['real']
a(2).real
#? []
a(2).upper
#? []
a(2).func
# -----------------
# class stuff
# -----------------
class A(object):
    a = ""
    a = 3
    #? ['real']
    a.real
    #? []
    a.upper
    #? []
    a.append
    a = list
    def __init__(self):
        self.b = ""
        self.b = 3
        #? ['real']
        self.b.real
        ##? []
        self.b.upper
        ##? []
        self.b.append

        self.b = list

    def before(self):
        self.a = 1
        #? int() str()
        self.a

        #? ['after']
        self.after

    def after(self):
        self.a = ''

#? list()
A.a

a = A()
#? ['after']
a.after
#? []
a.upper
#? []
a.append
#? []
a.real

#? ['append']
a.a.append
#? ['real']
a.a.real
#? ['upper']
a.a.upper

# -----------------
# class stuff
# -----------------

math = 3
import math
#? ['cosh']
math.cosh
#? []
math.real

math = 3
#? ['real']
math.real
#? []
math.cos

# do the same for star imports
cosh = 3
from math import *
# This doesn't work, but that's not a problem, star imports should be at the
# start of EVERY script!
##? []
cosh.real

cosh = 3
#? ['real']
cosh.real
