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
