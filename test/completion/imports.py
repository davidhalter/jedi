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
