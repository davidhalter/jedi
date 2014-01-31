"""
Handles operator precedence.
"""

from jedi.parser import representation as pr


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
    def __init__(self, left, operator, right=None):
        self.left = left
        self.operator = operator
        self.right = right


def create_precedence(expression_list, previous=None):
    element = next(expression_list, None)
    if element is None:
        return previous

    if isinstance(element, pr.Call):
        element = str(element.name)
    elif not isinstance(element, str):
        if previous is None:
            previous = element
        return create_precedence(expression_list, previous=previous)

    for term in PythonGrammar.order:
        if element in term:
            right = create_precedence(expression_list)
            if right is None:
                return previous
            else:
                return Precedence(previous, element, right)
