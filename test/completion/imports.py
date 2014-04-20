# -----------------
# own structure
# -----------------

# do separate scopes
def scope_basic():
    from import_tree import mod1

    #? int()
    mod1.a

    #? []
    import_tree.a

    #? []
    import_tree.mod1

    import import_tree
    #? str()
    import_tree.a

    #? []
    import_tree.mod1

def scope_pkg():
    import import_tree.mod1

    #? str()
    import_tree.a

    #? ['mod1']
    import_tree.mod1

    #? int()
    import_tree.mod1.a

def scope_nested():
    import import_tree.pkg.mod1

    #? str()
    import_tree.a

    #? list
    import_tree.pkg.a

    #? ['sqrt']
    import_tree.pkg.sqrt

    #? ['a', 'pkg']
    import_tree.

    #? float()
    import_tree.pkg.mod1.a

    import import_tree.random
    #? set
    import_tree.random.a

def scope_nested2():
    """Multiple modules should be indexable, if imported"""
    import import_tree.mod1
    import import_tree.pkg
    #? ['mod1']
    import_tree.mod1
    #? ['pkg']
    import_tree.pkg
    #? []
    import_tree.rename1

def from_names():
    #? ['mod1']
    from import_tree.pkg.
    #? ['path']
    from os.

def builtin_test():
    #? ['math']
    import math

def scope_from_import_variable():
    """
    All of them shouldn't work, because "fake" imports don't work in python
    without the use of ``sys.modules`` modifications (e.g. ``os.path`` see also
    github issue #213 for clarification.
    """
    #? 
    from import_tree.mod2.fake import a
    #? 
    from import_tree.mod2.fake import c

    #? 
    a
    #? 
    c

def scope_from_import_variable_with_parenthesis():
    from import_tree.mod2.fake import (
        a, c
    )

    #? 
    a
    #? 
    c

# -----------------
# std lib modules
# -----------------
import tokenize
#? ['tok_name']
tokenize.tok_name

from pyclbr import *

#? ['readmodule_ex']
readmodule_ex
import os

#? ['dirname']
os.path.dirname

#? os.path.join
from os.path import join

from os.path import (
    expanduser
)

#? os.path.expanduser
expanduser

from itertools import (tee,
                       islice)
#? ['islice']
islice

from functools import (partial, wraps)
#? ['wraps']
wraps

from keyword import kwlist, \
                    iskeyword
#? ['kwlist']
kwlist

#? []
from keyword import not_existing1, not_existing2

from tokenize import io
tokenize.generate_tokens

# -----------------
# builtins
# -----------------

import sys
#? ['prefix']
sys.prefix

#? ['append']
sys.path.append

from math import *
#? ['cos', 'cosh']
cos

def func_with_import():
    import time
    return time

#? ['sleep']
func_with_import().sleep

# -----------------
# completions within imports
# -----------------

#? ['sqlite3']
import sqlite3

#? ['classes']
import classes

#? ['timedelta']
from datetime import timedel

# should not be possible, because names can only be looked up 1 level deep.
#? []
from datetime.timedelta import resolution
#? []
from datetime.timedelta import 

#? ['Cursor']
from sqlite3 import Cursor

# -----------------
# relative imports
# -----------------

from .import_tree import mod1
#? int()
mod1.a

from ..import_tree import mod1
#? 
mod1.a

from .......import_tree import mod1
#? 
mod1.a

from .. import helpers
#? int()
helpers.sample_int

from ..helpers import sample_int as f
#? int()
f

from . import run
#? []
run.

from . import import_tree as imp_tree
#? str()
imp_tree.a

from . import datetime as mod1
#? []
mod1.

#? str()
imp_tree.a

#? ['some_variable']
from . import some_variable
#? ['arrays']
from . import arrays
#? []
from . import import_tree as ren


# -----------------
# special positions -> edge cases
# -----------------
import datetime

#? 6 datetime
from datetime.time import time

#? []
import datetime.
#? []
import datetime.date

#? 18 ['import']
from import_tree. import pkg
#? 17 ['mod1', 'mod2', 'random', 'pkg', 'rename1', 'rename2', 'recurse_class1', 'recurse_class2']
from import_tree. import pkg

#? 18 ['pkg']
from import_tree.p import pkg

#? 17 ['import_tree']
from .import_tree import 
#? 10 ['run']
from ..run import 
#? ['run']
from .. import run

#? []
from not_a_module import 

# self import
# this can cause recursions
from imports import *

#137
import json
#? 23 json.dump
from json import load, dump
#? 17 json.load
from json import load, dump
# without the from clause:
import json, datetime
#? 7 json
import json, datetime
#? 13 datetime
import json, datetime

# -----------------
# packages
# -----------------

from import_tree.mod1 import c
#? set
c

from import_tree import recurse_class1

#? ['a']
recurse_class1.C.a
# github #239 RecursionError
#? ['a']
recurse_class1.C().a

# -----------------
# Jedi debugging
# -----------------

# memoizing issues (check git history for the fix)
import not_existing_import

if not_existing_import:
    a = not_existing_import
else:
    a = not_existing_import
#? 
a
