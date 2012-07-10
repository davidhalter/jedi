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
# generators should be indexable!???
# -----------------
def get(self):
    yield 1
    yield ""

arr = []
for a in arr:
    arr += get()

#? int() str()
arr[0].
