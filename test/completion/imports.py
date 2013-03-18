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

from .. import base
#? int()
base.sample_int

from ..base import sample_int as f
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

#? 18 ['mod1', 'random', 'pkg', 'rename1', 'rename2', 'import']
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

# -----------------
# packages
# -----------------

from import_tree.mod1 import c
#? set
c
