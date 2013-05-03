# -----------------
# basic array lookups
# -----------------


#? int()
[1,""][0]
#? str()
[1,""][1]
#? int() str()
[1,""][2]
#? int() str()
[1,""][20]

a = list()
#? list()
[a][0]

#? list()
[[a,a,a]][2][100]

c = [[a,""]]
#? str()
c[0][1]

b = [6,7]

#? int()
b[8-7]

#? list()
b[8:]

#? list()
b[int():]


# -----------------
# iterable multiplication
# -----------------
a = ['']*2
#? list()
a

a = 2*2
#? int()
a

a = "a"*3
#? str()
a

# -----------------
# tuple assignments
# -----------------
a1, b1 = (1, "")
#? int()
a1
#? str()
b1

(a2, b2) = (1, "")
#? int()
a2
#? str()
b2

# list assignment
[list1, list2] = (1, "")
#? int()
list1
#? str()
list2

[list3, list4] = [1, ""]
#? int()
list3
#? str()
list4

# -----------------
# subtuple assignment
# -----------------
(a3, (b3, c3)) = (1, ("", list))
#? list
c3

a4, (b4, c4) = (1, ("", list))
#? list
c4
#? int()
a4
#? str()
b4


# -----------------
# unnessecary braces
# -----------------
#? int()
(1)
#? int()
((1))
#? int()
((1)+1)

u, v = 1, ""
#? int()
u

((u1, v1)) = 1, ""
#? int()
u1
#? int()
(u1)

(a), b = 1, ''
#? int()
a

def a(): return ''
#? str()
(a)()
#? str()
(a)().replace()
#? int()
(tuple).index()
#? int()
(tuple)().index()


# -----------------
# imbalanced sides
# -----------------
(f, g) = (1,)
#? int()
f
#? []
g.

(f, g, h) = (1,'')
#? int()
f
#? str()
g
#? []
h.

(f1, g1) = 1
#? []
f1.
#? []
g1.

(f, g) = (1,'',1.0)
#? int()
f
#? str()
g

# -----------------
# dicts
# -----------------
dic2 = {'asdf': 3, 'b': 'str'}
#? int()
dic2['asdf']

# string literal
#? int()
dic2[r'asdf']
#? int()
dic2[r'asdf']
#? int() str()
dic2['just_something']

def f():
    """ github #83 """
    r = {}
    r['status'] = (200, 'ok')
    return r

#? dict()
f()

# completion within dicts
#? 9 ['str']
{str: str}

# -----------------
# with variable as index
# -----------------
a = (1, "")
index = 1
#? str()
a[index]

# these should just ouput the whole array
index = int
#? int() str()
a[index]
index = int()
#? int() str()
a[index]

# dicts
index = 'asdf'

dic2 = {'asdf': 3, 'b': 'str'}
#? int()
dic2[index]

# -----------------
# __getitem__
# -----------------

class GetItem():
    def __getitem__(self, index):
        return 1.0

#? float()
GetItem()[0]

class GetItem():
    def __init__(self, el):
        self.el = el

    def __getitem__(self, index):
        return self.el

#? str()
GetItem("")[1]

# -----------------
# conversions
# -----------------

a = [1, ""]
#? int() str()
list(a)[1]

#? int() str()
list(a)[0]
#? 
set(a)[0]

#? int() str()
list(set(a))[1]
#? int() str()
list(list(set(a)))[1]

# does not yet work, because the recursion catching is not good enough (catches # to much)
#? int() str()
list(set(list(set(a))))[1]
#? int() str()
list(set(set(a)))[1]

# frozenset
#? int() str()
list(frozenset(a))[1]
#? int() str()
list(set(frozenset(a)))[1]

# iter
#? int() str()
list(iter(a))[1]
#? int() str()
list(iter(list(set(a))))[1]

# tuple
#? int() str()
tuple(a)[1]
#? int() str()
tuple(list(set(a)))[1]

#? int()
tuple({1})[0]
#? int()
tuple((1,))[0]

# implementation detail for lists, should not be visible
#? []
list().__iterable
