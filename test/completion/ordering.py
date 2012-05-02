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

b ="";b=1
#? ['real']
b.real
#? []
b.upper

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
        #? []
        self.b.upper
        #? []
        self.b.append

        self.b = list

    def before(self):
        self.a = 1
        #? ['real']
        self.a.real
        #? ['upper']
        self.a.upper

        #? ['after']
        self.after

    def after(self):
        self.a = ''

#? []
A.a.real
#? []
A.a.upper
#? ['append']
A.a.append

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
