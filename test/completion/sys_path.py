
import sys
import os
from os import dirname

sys.path.insert(0, '../../jedi')
sys.path.append(dirname(os.path.abspath('thirdparty' + os.path.sep + 'asdf')))

# modifications, that should fail:
# because of sys module
sys.path.append(sys.path[1] + '/thirdparty')
# syntax err
sys.path.append('a' +* '/thirdparty')

#? ['evaluate']
import evaluate

#? ['Evaluator']
evaluate.Evaluator

#? ['jedi_']
import jedi_

#? ['el']
jedi_.el
