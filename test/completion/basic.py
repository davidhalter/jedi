# -----------------
# cursor position
# -----------------
#? 0 int
int()
#? 3 int
int()
#? 4 str
int(str)


# -----------------
# should not complete
# -----------------
#? []
.
#? []
str..
#? []
a(0):.

# -----------------
# if/else/elif
# -----------------

if (random.choice([0, 1])):
    1
elif(random.choice([0, 1])):
    a = 3
else:
    a = ''
#? int() str()
a
def func():
    if random.choice([0, 1]):
        1
    elif(random.choice([0, 1])):
        a = 3
    else:
        a = ''
    #? int() str()
    return a
#? int() str()
func()

# -----------------
# keywords
# -----------------

#? list()
assert []

def focus_return():
    #? list()
    return []


# -----------------
# for loops
# -----------------

for a in [1,2]:
    #? int()
    a

for a1 in 1,"":
    #? int() str()
    a1

for a3, b3 in (1,""), (1,""), (1,""):
    #? int()
    a3
    #? str()
    b3

for a4, (b4, c4) in (1,("", list)), (1,("", list)):
    #? int()
    a4
    #? str()
    b4
    #? list
    c4

a = []
for i in [1,'']:
    #? int() str()
    i
    a += [i]

#? int() str()
a[0]

for i in list([1,'']):
    #? int() str()
    i

#? int() str()
for x in [1,'']: x

a = []
b = [1.0,'']
for i in b:
    a += [i]

#? float() str()
a[0]

for i in [1,2,3]:
    #? int()
    i
else:
    i


# -----------------
# range()
# -----------------
for i in range(10):
    #? int()
    i

# -----------------
# ternary operator
# -----------------

a = 3
b = '' if a else set()
#? str() set()
b

def ret(a):
    return ['' if a else set()]

#? str() set()
ret(1)[0]
#? str() set()
ret()[0]

# -----------------
# with statements
# -----------------

with open('') as f:
    #? ['closed']
    f.closed
    for line in f:
        #? str()
        line

with open('') as f1, open('') as f2:
    #? ['closed']
    f1.closed
    #? ['closed']
    f2.closed


# -----------------
# global vars
# -----------------

def global_define():
    global global_var_in_func
    global_var_in_func = 3

#? int()
global_var_in_func

# -----------------
# within docstrs
# -----------------

def a():
    """
    #? ['global_define']
    global_define
    """
    pass

#?
# str literals in comment """ upper

# -----------------
# magic methods
# -----------------

class A(object): pass
class B(): pass

#? ['__init__']
A.__init__
#? ['__init__']
B.__init__

#? ['__init__']
int().__init__

# -----------------
# comments
# -----------------

class A():
    def __init__(self):
        self.hello = {}  # comment shouldn't be a string
#? dict()
A().hello

# -----------------
# unicode
# -----------------
a = 'smörbröd'
#? str()
a
xyz = 'smörbröd.py'
if 1:
    #? str()
    xyz

# -----------------
# exceptions
# -----------------
try:
    import math
except ImportError as i_a:
    #? ['i_a']
    i_a
    #? ImportError()
    i_a
try:
    import math
except ImportError, i_b:
    # TODO check this only in Python2
    ##? ['i_b']
    i_b
    ##? ImportError()
    i_b


class MyException(Exception):
    def __init__(self, my_attr):
        self.my_attr = my_attr

try:
    raise MyException(1)
except MyException as e:
    #? ['my_attr']
    e.my_attr
    #? 22 ['my_attr']
    for x in e.my_attr:
        pass


# -----------------
# continuations
# -----------------

foo = \
1
#? int()
foo

# -----------------
# module attributes
# -----------------

# Don't move this to imports.py, because there's a star import.
#? str()
__file__
#? ['__file__']
__file__
