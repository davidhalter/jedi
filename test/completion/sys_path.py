
import sys
import os
from os import dirname

sys.path.insert(0, '../../jedi')
sys.path.append(dirname(os.path.abspath('thirdparty' + os.path.sep + 'asdf')))

# modifications, that should fail:
# syntax err
sys.path.append('a' +* '/thirdparty')

#? ['evaluate']
import evaluate

#? ['evaluator_function_cache']
evaluate.Evaluator_fu

# Those don't work because dirname and abspath are not properly understood.
##? ['jedi_']
import jedi_

##? ['el']
jedi_.el
