"""
Handles operator precedence.
"""

from jedi.parser import representation as pr
from jedi import debug
from jedi.common import PushBackIterator


class PythonGrammar(object):
    """
    Some kind of mirror of http://docs.python.org/3/reference/grammar.html.
    """

    class AtStart(tuple):
        pass

    class MultiPart(str):
        def __new__(cls, first, second):
            self = str.__new__(cls, first)
            self.second = second

    factor = AtStart(('+', '-', '~'))
    power = '**',
    term = '*', '/', '%', '//'
    arith_expr = '+', '-'

    shift_expr = '<<', '>>'
    and_expr = '&',
    xor_expr = '^',
    expr = '|',

    comparison = ('<', '>', '==', '>=', '<=', '!=', 'in',
                  MultiPart('not', 'in'), 'is', MultiPart('is', 'not'))

    not_test = AtStart(('not',))
    and_test = 'and',
    or_test = 'or',

    #test = or_test ['if' or_test 'else' test] | lambdef

    #sliceop = ':' [test]
    #subscript = test | [test] ':' [test] [sliceop]
    order = (factor, power, term, arith_expr, shift_expr, and_expr, xor_expr,
             expr, comparison, not_test, and_test, or_test)


class Precedence(object):
    def __init__(self, left, operator, right):
        self.left = left
        self.operator = operator
        self.right = right


def create_precedence(expression_list):
    def get_op(current, expression_list):
        for element in expression_list:
            return
            if not isinstance(obj, str):
                debug.warning('normal element in place of operator: %s', element)
                continue

    def is_operator(obj):
        if isinstance(obj, pr.Call):
            element = str(obj.name)
        for term in PythonGrammar.order:
            pass
        return element

    def tokenize():
        pass

    new
    current = None
    exp_iterator = PushBackIterator(expression_list)
    for element in expression_list:
        op_name = element
        if isinstance(element, pr.Call):
            op_name = str(element.name)
        current = s
        if isinstance(element, pr.Call):
            x = str(element.name)
        new = _process_element(element, expression_list)
        if current is None:
            current = new
        else:
            current = _process_element(element, expression_list)
    return current


def _process_element(element, expression_list, previous=None):
    if element is None:
        return previous

    if isinstance(element, pr.Call):
        element = str(element.name)
    elif not isinstance(element, str):
        if previous is None:
            previous = element
        return _process_element(expression_list, previous=previous)

    for term in PythonGrammar.order:
        if element in term:
            right = _process_element(expression_list)
            if right is None:
                return previous
            else:
                return Precedence(previous, element, right)
