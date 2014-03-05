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

if 1:
    1
elif(3):
    a = 3
else:
    a = ''
#? int() str()
a
def func():
    if 1:
        1
    elif(3):
        a = 3
    else:
        a = ''
    #? int() str()
    return a
#? int() str()
func()

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

# -----------------
# range()
# -----------------
for i in range(10):
    #? int()
    i

# -----------------
# list comprehensions
# -----------------

# basics:

a = ['' for a in [1]]
#? str()
a[0]

a = [a for a in [1]]
#? int()
a[0]

a = [a for a in 1,2]
#? int()
a[0]

a = [a for a,b in [(1,'')]]
#? int()
a[0]

arr = [1,'']
a = [a for a in arr]
#? int() str()
a[0]

a = [a if 1.0 else '' for a in [1] if [1.0]]
#? int() str()
a[0]

# with a dict literal
#? str()
[a for a in {1:'x'}][0]

##? str()
{a-1:b for a,b in {1:'a', 3:1.0}.items()}[0]

# -----------------
# nested list comprehensions
# -----------------

b = [a for arr in [[1]] for a in arr]
#? int()
b[0]

b = [a for arr in [[1]] if '' for a in arr if '']
#? int()
b[0]

b = [b for arr in [[[1.0]]] for a in arr for b in a]
#? float()
b[0]

# jedi issue #26
#? list()
a = [[int(v) for v in line.strip().split() if v] for line in ["123", "123", "123"] if line]
#? list()
a[0]
#? int()
a[0][0]

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
    #? ['i_b']
    i_b
    #? ImportError()
    i_b

# -----------------
# continuations
# -----------------

foo = \
1
#? int()
foo
