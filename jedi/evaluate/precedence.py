"""
Handles operator precedence.
"""

from jedi._compatibility import unicode
from jedi.parser import representation as pr
from jedi import debug
from jedi.common import PushBackIterator
from jedi.evaluate.compiled import CompiledObject, create, builtin


class PythonGrammar(object):
    """
    Some kind of mirror of http://docs.python.org/3/reference/grammar.html.
    """

    class MultiPart(str):
        def __new__(cls, first, second):
            self = str.__new__(cls, first)
            self.second = second
            return self

        def __str__(self):
            return str.__str__(self) + ' ' + self.second

    FACTOR = '+', '-', '~'
    POWER = '**',
    TERM = '*', '/', '%', '//'
    ARITH_EXPR = '+', '-'

    SHIFT_EXPR = '<<', '>>'
    AND_EXPR = '&',
    XOR_EXPR = '^',
    EXPR = '|',

    COMPARISON = ('<', '>', '==', '>=', '<=', '!=', 'in',
                  MultiPart('not', 'in'), MultiPart('is', 'not'), 'is')

    NOT_TEST = 'not',
    AND_TEST = 'and',
    OR_TEST = 'or',

    #TEST = or_test ['if' or_test 'else' test] | lambdef

    TERNARY = 'if',
    SLICE = ':',

    ORDER = (POWER, TERM, ARITH_EXPR, SHIFT_EXPR, AND_EXPR, XOR_EXPR,
             EXPR, COMPARISON, AND_TEST, OR_TEST, TERNARY, SLICE)

    FACTOR_PRIORITY = 0  # highest priority
    LOWEST_PRIORITY = len(ORDER)
    NOT_TEST_PRIORITY = LOWEST_PRIORITY - 4  # priority only lower for `and`/`or`
    SLICE_PRIORITY = LOWEST_PRIORITY - 1  # priority only lower for `and`/`or`


class Precedence(object):
    def __init__(self, left, operator, right):
        self.left = left
        self.operator = operator
        self.right = right

    def parse_tree(self, strip_literals=False):
        def process(which):
            try:
                which = which.parse_tree(strip_literals)
            except AttributeError:
                pass
            if strip_literals and isinstance(which, pr.Literal):
                which = which.value
            return which

        return (process(self.left), self.operator, process(self.right))

    def __repr__(self):
        return '(%s %s %s)' % (self.left, self.operator, self.right)


class TernaryPrecedence(Precedence):
    def __init__(self, left, operator, right, check):
        super(TernaryPrecedence, self).__init__(left, operator, right)
        self.check = check


def create_precedence(expression_list):
    iterator = PushBackIterator(iter(expression_list))
    return _check_operator(iterator)


def _syntax_error(element, msg='SyntaxError in precedence'):
    debug.warning('%s: %s, %s' % (msg, element, element.start_pos))


def _get_number(iterator, priority=PythonGrammar.LOWEST_PRIORITY):
    el = next(iterator)
    if isinstance(el, pr.Operator):
        if el in PythonGrammar.FACTOR:
            right = _get_number(iterator, PythonGrammar.FACTOR_PRIORITY)
        elif el in PythonGrammar.NOT_TEST \
                and priority >= PythonGrammar.NOT_TEST_PRIORITY:
            right = _get_number(iterator, PythonGrammar.NOT_TEST_PRIORITY)
        elif el in PythonGrammar.SLICE \
                and priority >= PythonGrammar.SLICE_PRIORITY:
            iterator.push_back(el)
            return None
        else:
            _syntax_error(el)
            return _get_number(iterator, priority)
        return Precedence(None, el, right)
    else:
        return el


def _check_operator(iterator, priority=PythonGrammar.LOWEST_PRIORITY):
    try:
        left = _get_number(iterator, priority)
    except StopIteration:
        return None

    for el in iterator:
        if not isinstance(el, pr.Operator):
            _syntax_error(el)
            continue

        operator = None
        for check_prio, check in enumerate(PythonGrammar.ORDER):
            if check_prio >= priority:
                # respect priorities.
                iterator.push_back(el)
                return left

            try:
                match_index = check.index(el)
            except ValueError:
                continue

            match = check[match_index]
            if isinstance(match, PythonGrammar.MultiPart):
                next_tok = next(iterator)
                if next_tok != match.second:
                    iterator.push_back(next_tok)
                    if el == 'is':  # `is not` special case
                        match = 'is'
                    else:
                        continue

            operator = match
            break

        if operator is None:
            _syntax_error(el)
            continue

        if operator in PythonGrammar.POWER:
            check_prio += 1  # to the power of is right-associative
        elif operator in PythonGrammar.TERNARY:
            try:
                middle = []
                for each in iterator:
                    if each == 'else':
                        break
                    middle.append(each)
                middle = create_precedence(middle)
            except StopIteration:
                _syntax_error(operator, 'SyntaxError ternary incomplete')
        right = _check_operator(iterator, check_prio)
        if right is None and not operator in PythonGrammar.SLICE:
            _syntax_error(iterator.current, 'SyntaxError operand missing')
        else:
            if operator in PythonGrammar.TERNARY:
                left = TernaryPrecedence(left, str(operator), right, middle)
            else:
                left = Precedence(left, str(operator), right)
    return left


def _literals_to_types(evaluator, result):
    # Changes literals ('a', 1, 1.0, etc) to its type instances (str(),
    # int(), float(), etc).
    for i, r in enumerate(result):
        if is_literal(r):
            # Literals are only valid as long as the operations are
            # correct. Otherwise add a value-free instance.
            cls = builtin.get_by_name(r.name)
            result[i] = evaluator.execute(cls)[0]
    return list(set(result))


def calculate(evaluator, left_result, operator, right_result):
    result = []
    if left_result is None and right_result:
        # cases like `-1` or `1 + ~1`
        for right in right_result:
            result.append(_factor_calculate(evaluator, operator, right))
        return result
    else:
        if not left_result or not right_result:
            # illegal slices e.g. cause left/right_result to be None
            result = (left_result or []) + (right_result or [])
            result = _literals_to_types(evaluator, result)
        else:
            # I don't think there's a reasonable chance that a string
            # operation is still correct, once we pass something like six
            # objects.
            if len(left_result) * len(right_result) > 6:
                result = _literals_to_types(evaluator, left_result + right_result)
            else:
                for left in left_result:
                    for right in right_result:
                        result += _element_calculate(evaluator, left, operator, right)
    return result


def _factor_calculate(evaluator, operator, right):
    if _is_number(right):
        if operator == '-':
            return create(evaluator, -right.obj)
    return right


def _is_number(obj):
    return isinstance(obj, CompiledObject) \
        and isinstance(obj.obj, (int, float))


def _is_string(obj):
    return isinstance(obj, CompiledObject) \
        and isinstance(obj.obj, (str, unicode))


def is_literal(obj):
    return _is_number(obj) or _is_string(obj)


def _element_calculate(evaluator, left, operator, right):
    if operator == '*':
        # for iterables, ignore * operations
        from jedi.evaluate import iterable
        if isinstance(left, iterable.Array) or _is_string(left):
            return [left]
    elif operator == '+':
        if _is_number(left) and _is_number(right) or _is_string(left) and _is_string(right):
            return [create(evaluator, left.obj + right.obj)]
    elif operator == '-':
        if _is_number(left) and _is_number(right):
            return [create(evaluator, left.obj - right.obj)]
    return [left, right]
