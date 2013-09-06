"""
std library stuff
"""

# -----------------
# builtins
# -----------------
arr = ['']

#? str()
sorted(arr)[0]

#? str()
next(reversed(arr))

#? str()
next(open(''))

# -----------------
# re
# -----------------
import re
c = re.compile(r'a')
# re.compile should not return str -> issue #68
#? []
c.startswith
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


# -----------------
# sqlite3 (#84)
# -----------------

import sqlite3
#? sqlite3.Connection()
con = sqlite3.connect()
#? sqlite3.Cursor()
c = con.cursor()
#? sqlite3.Row()
row = c.fetchall()[0]
#? str()
row.keys()[0]

def huhu(db):
    """
        :type db: sqlite3.Connection
        :param db: the db connection
    """
    #? sqlite3.Connection()
    db
