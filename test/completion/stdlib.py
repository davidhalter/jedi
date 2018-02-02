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
next(reversed(arr))

# should not fail if there's no return value.
def yielder():
    yield None

#? None
next(reversed(yielder()))

# empty reversed should not raise an error
#?
next(reversed())

#? str()
next(open(''))

#? int()
{'a':2}.setdefault('a', 3)

# Compiled classes should have the meta class attributes.
#? ['__itemsize__']
tuple.__itemsize__

# -----------------
# type() calls with one parameter
# -----------------
#? int
type(1)
#? int
type(int())
#? type
type(int)
#? type
type(type)
#? list
type([])

def x():
    yield 1
generator = type(x())
#? generator
type(x for x in [])
#? type(x)
type(lambda: x)

import math
import os
#? type(os)
type(math)
class X(): pass
#? type
type(X)

if os.path.isfile():
    #? ['abspath']
    fails = os.path.abspath


with open('foo') as f:
    for line in f.readlines():
        #? str()
        line
# -----------------
# enumerate
# -----------------
for i, j in enumerate(["as", "ad"]):
    #? int()
    i
    #? str()
    j

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

#? weakref.ref()
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

def function(a, b):
    return a, b
a = functools.partial(function, 0)

#? int()
a('')[0]
#? str()
a('')[1]

kw = functools.partial(function, b=1.0)
tup = kw(1)
#? int()
tup[0]
#? float()
tup[1]

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

# -----------------
# hashlib
# -----------------

import hashlib

#? ['md5']
hashlib.md5

# -----------------
# copy
# -----------------

import copy
#? int()
copy.deepcopy(1)

#?
copy.copy()

# -----------------
# json
# -----------------

# We don't want any results for json, because it depends on IO.
import json
#?
json.load('asdf')
#?
json.loads('[1]')

# -----------------
# random
# -----------------

import random
class A(object):
    def say(self): pass
class B(object):
    def shout(self): pass
cls = random.choice([A, B])
#? ['say', 'shout']
cls().s

# -----------------
# random
# -----------------

import zipfile
z = zipfile.ZipFile("foo")
# It's too slow. So we don't run it at the moment.
##? ['upper']
z.read('name').upper

# -----------------
# contextlib
# -----------------

import contextlib
with contextlib.closing('asd') as string:
    #? str()
    string

# -----------------
# shlex
# -----------------

# Github issue #929
import shlex
qsplit = shlex.split("foo, ferwerwerw werw werw e")
for part in qsplit:
    #? str() None
    part
