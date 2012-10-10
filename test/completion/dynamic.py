"""
This is used for dynamic object completion.
Jedi tries to guess the types with a backtracking approach.
"""
def func(a):
    #? int() str()
    return a

#? int()
func(1)

func

int(1) + (int(2))+ func('')

# Again the same function, but with another call.
def func(a):
    #? float()
    return a

func(1.0)

# Again the same function, but with no call.
def func(a):
    #? 
    return a

def func(a):
    #? float()
    return a
str(func(1.0))

# -----------------
# *args, **args
# -----------------
def arg(*args):
    #? tuple()
    args
    #? int()
    args[0]

arg(1,"")
# -----------------
# decorators
# -----------------
def def_func(f):
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)
    return wrapper

@def_func
def func(c):
    #? str()
    return c

#? str()
func("str")

@def_func
def func(c=1):
    #? int() float()
    return c

func(1.0)

# -----------------
# classes
# -----------------

class A():
    def __init__(self, a):
        #? str()
        a

A("s")

class A():
    def __init__(self, a):
        #? int()
        a
        self.a = a

    def test(self, a):
        #? float()
        a
        self.c = self.test2()

    def test2(self):
        #? int()
        return self.a

    def test3(self):
        #? int()
        self.test2()
        #? int()
        self.c

A(3).test(2.0)
A(3).test2()

# -----------------
# list.append
# -----------------
arr = []
for a in [1,2]:
    arr.append(a);

arr.append  # should not cause an exception
arr.append()  # should not cause an exception

#? int()
arr[10]

arr = [tuple()]
for a in [1,2]:
    arr.append(a);

#? int() tuple()
arr[10]
#? int()
arr[10].index()

arr = list([])
arr.append(1)
#? int()
arr[0]

# -----------------
# list.insert
# -----------------
arr = [""]
arr.insert(0, 1.0)

# on exception due to this, please!
arr.insert(0)
arr.insert()

#? float() str()
arr[10]

for a in arr:
    #? float() str()
    a

#? float() str()
list(arr)[10]

# -----------------
# set.add
# -----------------
st = {1.0}
for a in [1,2]:
    st.add(a)

st.append('')  # lists should not have an influence

st.add  # should not cause an exception
st.add()

# -----------------
# list.extend / set.update
# -----------------

arr = [1.0]
arr.extend([1,2,3])
arr.extend([])
arr.extend("")  # should ignore

#? float() int()
arr[100]

a = set(arr)
a.update(list(["", 1]))

#? float() int() str()
list(a)[0]
# -----------------
# set/list initialized as functions
# -----------------

st = set()
st.add(1)

#? int()
for s in st: s

lst = list()
lst.append(1)

#? int()
for i in lst: i

# -----------------
# renames / type changes
# -----------------
arr = []
arr2 = arr
arr2.append('')
#? str()
arr2[0]


st = {1.0}
st.add(1)
lst = list(st)

lst.append('')

#? float() int() str()
lst[0]

lst = [1]
lst.append(1.0)
s = set(lst)
s.add("")
lst = list(s)
lst.append({})

#? dict() int() float() str()
lst[0]

# should work with tuple conversion, too.
#? dict() int() float() str()
tuple(lst)[0]

# but not with an iterator
#? 
iter(lst)[0]

# -----------------
# complex including +=
# -----------------
class C(): pass
class D(): pass
class E(): pass
lst = [1]
lst.append(1.0)
lst += [C]
s = set(lst)
s.add("")
s += [D]
lst = list(s)
lst.append({})
lst += [E]

##? dict() int() float() str() C D E
lst[0]

# -----------------
# functions
# -----------------

def arr_append(arr4, a):
    arr4.append(a)

def add_to_arr(arr2, a):
    arr2.append(a)
    return arr2

def app(a):
    arr3.append(a)

arr3 = [1.0]
res = add_to_arr(arr3, 1)
arr_append(arr3, 'str')
app(set())

#? float() str() int() set()
arr3[10]

#? float() str() int() set()
res[10]

# -----------------
# returns, special because the module dicts are not correct here.
# -----------------
def blub():
    a = []
    a.append(1.0)
    #? float()
    a[0]
    return a

#? float()
blub()[0]

# list with default
def blub():
    a = list([1])
    a.append(1.0)
    return a

#? int() float()
blub()[0]

# empty list
def blub():
    a = list()
    a.append(1.0)
    return a
#? float()
blub()[0]

# with if
def blub():
    if 1:
        a = []
        a.append(1.0)
        return a

#? float()
blub()[0]

# with else clause
def blub():
    if 1:
        1
    else:
        a = []
        a.append(1)
        return a

#? int()
blub()[0]
# -----------------
# returns, the same for classes
# -----------------
class C():
    def blub(self, b):
        if 1:
            a = []
            a.append(b)
            return a

    def blub2(self):
        """ mapper function """
        a = self.blub(1.0)
        #? float()
        a[0]
        return a

    def class_arr(self, el):
        self.a = []
        self.a.append(el)
        #? int()
        self.a[0]
        return self.a

#? int()
C().blub(1)[0]
#? float()
C().blub2(1)[0]

#? int()
C().a[0]
#? int()
C().class_arr(1)[0]

# -----------------
# array recursions
# -----------------

a = set([1.0])
a.update(a)
a.update([1])

#? float() int()
list(a)[0]

def first(a):
    b = []
    b.append(a)
    b.extend(second(a))
    return list(b)

def second(a):
    b = []
    b.extend(first(a))
    return list(b)

#? float()
first(1.0)[0]

def third():
    b = []
    b.extend
    extend()
    b.extend(first())
    return list(b)
#? 
third()[0]
