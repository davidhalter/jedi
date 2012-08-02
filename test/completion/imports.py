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

    #? ['a', 'pkg']
    import_tree.

    #? float()
    import_tree.pkg.mod1.a

    #? ['a', 'pkg']
    import_tree.

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
import sqlite

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
