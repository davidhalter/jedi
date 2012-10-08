# -----------------
# non array
# -----------------

#? ['imag']
int.imag

#? []
int.is_integer

#? ['is_integer']
float.is_int

#? ['is_integer']
1.0.is_integer

#? ['upper']
"".upper

#? ['upper']
r"".upper

# strangely this didn't work, because the = is used for assignments
#? ['upper']
"=".upper
a = "="
#? ['upper']
a.upper


# -----------------
# lists
# -----------------
arr = []
#? ['append']
arr.app

#? ['append']
list().app
#? ['append']
[].append

arr2 = [1,2,3]
#? ['append']
arr2.app

#? int()
arr.count(1)

# -----------------
# dicts
# -----------------
dic = {}

#? ['copy', 'clear']
dic.c

dic2 = dict(a=1, b=2)
#? ['pop', 'popitem']
dic2.p
#? ['popitem']
{}.popitem

dic2 = {'asdf': 3}
#? ['popitem']
dic2.popitem

#? int()
dic2['asdf']

# -----------------
# set
# -----------------
set_t = {1,2}

#? ['clear', 'copy']
set_t.c

set_t2 = set()

#? ['clear', 'copy']
set_t2.c

# -----------------
# tuples
# -----------------
tup = ('',2)

#? ['count']
tup.c

tup2 = tuple()
#? ['index']
tup2.i
#? ['index']
().i

tup3 = 1,""
#? ['index']
tup3.index

tup4 = 1,""
#? ['index']
tup4.index
