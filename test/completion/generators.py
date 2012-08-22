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

g = iter(Get())
#? int() str()
next(g)

g = iter([1.0])
#? float()
next(g)

# -----------------
# __next__
# -----------------
class Counter:
    def __init__(self, low, high):
        self.current = low
        self.high = high

    def __iter__(self):
        return self

    def next(self):
        """ need to have both __next__ and next, because of py2/3 testing """
        return self.__next__()

    def __next__(self):
        if self.current > self.high:
            raise StopIteration
        else:
            self.current += 1
            return self.current - 1


for c in Counter(3, 8):
    #? int()
    print c

# -----------------
# tuples
# -----------------
def gen():
    if a:
        yield 1, ""
    else:
        yield 2, 1.0


a, b = next(gen())
#? int()
a
#? str() float()
b
