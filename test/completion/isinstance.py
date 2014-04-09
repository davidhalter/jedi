if isinstance(i, str):
    #? str()
    i

if isinstance(j, (str, int)):
    #? str() int()
    j

while isinstance(k, (str, int)):
    #? str() int()
    k

if not isinstance(k, (str, int)):
    #? 
    k

while not isinstance(k, (str, int)):
    #? 
    k

assert isinstance(ass, int)
#? int()
ass

assert isinstance(ass, str)
assert not isinstance(ass, int)

if 2:
    #? str()
    ass

# -----------------
# in functions
# -----------------

import datetime


def fooooo(obj):
    if isinstance(obj, datetime.datetime):
        #? datetime.datetime
        obj


def fooooo2(obj):
    if isinstance(obj, datetime.datetime):
        return obj
    else:
        return 1

#? int() datetime.datetime
fooooo2('')


# -----------------
# Names with multiple indices.
# -----------------

class Test():
    def __init__(self, testing):
        if isinstance(testing, str):
            self.testing = testing
        else:
            self.testing = 10

    def boo(self):
        if isinstance(self.testing, str):
            ##? str()
            self.testing
