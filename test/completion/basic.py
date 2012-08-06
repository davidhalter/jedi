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
    a += [i]

#? int() str()
a[0]

a = []
b = [1.0,'']
for i in b:
    a += [i]

#? float() str()
a[0]

# -----------------
# list comprehensions
# -----------------

a = ['' for abc in [1]]

#? str()
a[0]


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
