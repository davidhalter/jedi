# -----------------
# yield statement
# -----------------

def gen():
    yield 1
    yield ""

gen_exe = gen()
#? ['upper']
next(gen_exe).upper
#? ['real']
next(gen_exe).real
#? int() str()
next(gen_exe)

#? int() str() list
next(gen_exe, list)

# -----------------
# generators should be indexable?
# -----------------
def get(self):
    yield 1
    yield ""

arr = []
for a in arr:
    arr += get()

#? int() str()
arr[0].
