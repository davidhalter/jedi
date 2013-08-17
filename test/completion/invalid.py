"""
This file is less about the results and much more about the fact, that no
exception should be thrown.

Basically this file could change depending on the current implementation. But
there should never be any errors.
"""

# wait until keywords are out of definitions (pydoc function).
##? 5 
's'()

#? ['upper']
str()).upper

# -----------------
# funcs
# -----------------
def asdf(a or b): # multiple param names
    return a

#? int()
asdf(2)

from a import (b
def blub():
    return 0
def openbrace():
    asdf = 3
     asdf
    asdf(
    #? int()
    asdf
    return 1

#? int()
openbrace()

blub([
#? int()
openbrace()

def indentfault():
    asd(
 indentback

#? []
indentfault().

def openbrace2():
    asd(
def normalfunc():
    return 1

#? int()
normalfunc()

# dots in param
def f(seq1...=None):
    return seq1
#? int()
f(1)

@
def test_empty_decorator():
    return 1

#? int()
test_empty_decorator()

# -----------------
# flows
# -----------------

# first part not complete (raised errors)
if a
    a
else:
    #? ['AttributeError']
    AttributeError

try
#? ['AttributeError']
except AttributeError
    pass
finally:
    pass

#? ['isinstance']
if isi
try:
    except TypeError:
        #? str()
        ""

# wrong ternary expression
a = 1 if
#? int()
a

for for_local in :
    for_local
#? ['for_local']
for_local
#? 
for_local


# -----------------
# list comprehensions
# -----------------

a2 = [for a2 in [0]]
#? 
a2[0]

a3 = [for xyz in]
#? 
a3[0]

a3 = [a4 for in 'b']
#? str()
a3[0]

a3 = [a4 for a in for x in y]
#? 
a3[0]

a = [for a in
def break(): pass

#? 
a[0]

a = [a for a in [1,2]
def break(): pass
#? int()
a[0]

#? []
int()).

# -----------------
# keywords
# -----------------

#! []
as

def empty_assert():
    x = 3
    assert
    #? int()
    x

import datetime as 
