"""
Handles operator precedence.
"""
import operator as op

from jedi._compatibility import unicode
from jedi.parser.python import tree
from jedi import debug
from jedi.evaluate.compiled import CompiledObject, create, builtin_from_name
from jedi.evaluate import analysis

# Maps Python syntax to the operator module.
COMPARISON_OPERATORS = {
    '==': op.eq,
    '!=': op.ne,
    'is': op.is_,
    'is not': op.is_not,
    '<': op.lt,
    '<=': op.le,
    '>': op.gt,
    '>=': op.ge,
}


def literals_to_types(evaluator, result):
    # Changes literals ('a', 1, 1.0, etc) to its type instances (str(),
    # int(), float(), etc).
    new_result = set()
    for typ in result:
        if is_literal(typ):
            # Literals are only valid as long as the operations are
            # correct. Otherwise add a value-free instance.
            cls = builtin_from_name(evaluator, typ.name.string_name)
            new_result |= cls.execute_evaluated()
        else:
            new_result.add(typ)
    return new_result


def calculate_children(evaluator, context, children):
    """
    Calculate a list of children with operators.
    """
    iterator = iter(children)
    types = context.eval_node(next(iterator))
    for operator in iterator:
        right = next(iterator)
        if operator.type == 'comp_op':  # not in / is not
            operator = ' '.join(str(c.value) for c in operator.children)

        # handle lazy evaluation of and/or here.
        if operator in ('and', 'or'):
            left_bools = set([left.py__bool__() for left in types])
            if left_bools == set([True]):
                if operator == 'and':
                    types = context.eval_node(right)
            elif left_bools == set([False]):
                if operator != 'and':
                    types = context.eval_node(right)
            # Otherwise continue, because of uncertainty.
        else:
            types = calculate(evaluator, context, types, operator,
                              context.eval_node(right))
    debug.dbg('calculate_children types %s', types)
    return types


def calculate(evaluator, context, left_result, operator, right_result):
    result = set()
    if not left_result or not right_result:
        # illegal slices e.g. cause left/right_result to be None
        result = (left_result or set()) | (right_result or set())
        result = literals_to_types(evaluator, result)
    else:
        # I don't think there's a reasonable chance that a string
        # operation is still correct, once we pass something like six
        # objects.
        if len(left_result) * len(right_result) > 6:
            result = literals_to_types(evaluator, left_result | right_result)
        else:
            for left in left_result:
                for right in right_result:
                    result |= _element_calculate(evaluator, context, left, operator, right)
    return result


def factor_calculate(evaluator, types, operator):
    """
    Calculates `+`, `-`, `~` and `not` prefixes.
    """
    for typ in types:
        if operator == '-':
            if _is_number(typ):
                yield create(evaluator, -typ.obj)
        elif operator == 'not':
            value = typ.py__bool__()
            if value is None:  # Uncertainty.
                return
            yield create(evaluator, not value)
        else:
            yield typ


def _is_number(obj):
    return isinstance(obj, CompiledObject) \
        and isinstance(obj.obj, (int, float))


def is_string(obj):
    return isinstance(obj, CompiledObject) \
        and isinstance(obj.obj, (str, unicode))


def is_literal(obj):
    return _is_number(obj) or is_string(obj)


def _is_tuple(obj):
    from jedi.evaluate import iterable
    return isinstance(obj, iterable.AbstractSequence) and obj.array_type == 'tuple'


def _is_list(obj):
    from jedi.evaluate import iterable
    return isinstance(obj, iterable.AbstractSequence) and obj.array_type == 'list'


def _element_calculate(evaluator, context, left, operator, right):
    from jedi.evaluate import iterable, instance
    l_is_num = _is_number(left)
    r_is_num = _is_number(right)
    if operator == '*':
        # for iterables, ignore * operations
        if isinstance(left, iterable.AbstractSequence) or is_string(left):
            return set([left])
        elif isinstance(right, iterable.AbstractSequence) or is_string(right):
            return set([right])
    elif operator == '+':
        if l_is_num and r_is_num or is_string(left) and is_string(right):
            return set([create(evaluator, left.obj + right.obj)])
        elif _is_tuple(left) and _is_tuple(right) or _is_list(left) and _is_list(right):
            return set([iterable.MergedArray(evaluator, (left, right))])
    elif operator == '-':
        if l_is_num and r_is_num:
            return set([create(evaluator, left.obj - right.obj)])
    elif operator == '%':
        # With strings and numbers the left type typically remains. Except for
        # `int() % float()`.
        return set([left])
    elif operator in COMPARISON_OPERATORS:
        operation = COMPARISON_OPERATORS[operator]
        if isinstance(left, CompiledObject) and isinstance(right, CompiledObject):
            # Possible, because the return is not an option. Just compare.
            left = left.obj
            right = right.obj

        try:
            result = operation(left, right)
        except TypeError:
            # Could be True or False.
            return set([create(evaluator, True), create(evaluator, False)])
        else:
            return set([create(evaluator, result)])
    elif operator == 'in':
        return set()

    def check(obj):
        """Checks if a Jedi object is either a float or an int."""
        return isinstance(obj, instance.CompiledInstance) and \
            obj.name.string_name in ('int', 'float')

    # Static analysis, one is a number, the other one is not.
    if operator in ('+', '-') and l_is_num != r_is_num \
            and not (check(left) or check(right)):
        message = "TypeError: unsupported operand type(s) for +: %s and %s"
        analysis.add(context, 'type-error-operation', operator,
                     message % (left, right))

    return set([left, right])
