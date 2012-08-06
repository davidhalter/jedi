# -----------------
# yield statement
# -----------------

def gen():
    yield 1
    yield ""

gen_exe = gen()
#? int() str()
next(gen_exe)

#? int() str() list
next(gen_exe, list)

def gen_ret(value):
    yield value

#? int()
next(gen_ret(1))

#? []
next(gen_ret())

# -----------------
# generators should not be indexable
# -----------------
def get(param):
    yield 1
    yield ""

#? []
get()[0]

# -----------------
# __iter__
# -----------------
for a in get():
    #? int() str()
    a

class Get():
    def __iter__(self):
        yield 1
        yield ""

b = []
for a in Get():
    #? int() str()
    a
    b += [a]

#? list()
b
#? int() str()
b[0]
