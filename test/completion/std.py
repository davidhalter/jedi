"""
std library stuff
"""

# -----------------
# re
# -----------------
import re
c = re.compile(r'a')
#? int()
c.match().start()

#? int()
re.match(r'a', 'a').start()

for a in re.finditer('a', 'a'):
    #? int()
    a.start()

#? str()
re.sub('a', 'a')

# -----------------
# ref
# -----------------
import weakref

#? int()
weakref.proxy(1)

#? weakref.ref
weakref.ref(1)
#? int()
weakref.ref(1)()

# -----------------
# functools
# -----------------
import functools

basetwo = functools.partial(int, base=2)
#? int()
basetwo()

def a(a, b):
    return a, b
a = functools.partial(a, 0)

#? int()
a('')[0]
#? str()
a('')[1]

def my_decorator(f):
    @functools.wraps(f)
    def wrapper(*args, **kwds):
        return f(*args, **kwds)
    return wrapper

@my_decorator
def example(a):
    return a

#? str()
example('')
