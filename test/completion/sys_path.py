
import sys
import os
from os import dirname

sys.path.insert(0, '../../sith')
sys.path.append(dirname(os.path.abspath('thirdparty' + os.path.sep + 'asdf')))

# modifications, that should fail:
# because of sys module
sys.path.append(sys.path[1] + '/thirdparty')
# syntax err
sys.path.append('a' +* '/thirdparty')

#? ['evaluate']
import evaluate

#? ['goto']
evaluate.goto

#? ['sith_']
import sith_

#? ['el']
sith_.el
