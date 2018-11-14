# just for getting into the except - path of the importer when removing
# the inserted path to this module
import sys
del sys.path[0]

from jedi.evaluate.base_context import NO_CONTEXTS

def jedi_importer_test2a(*a):
    return NO_CONTEXTS