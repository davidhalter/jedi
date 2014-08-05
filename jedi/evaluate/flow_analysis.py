from jedi.parser.representation import Flow


class Status(object):
    def __init__(self, value):
        self._value = value

    def __eq__(self, other):
        return self._value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __and__(self, other):
        if UNSURE in (self, other):
            return other
        else:
            return REACHABLE if self._value and other._value else NOT_REACHABLE


NOT_REACHABLE = Status(True)
REACHABLE = Status(False)
UNSURE = Status(None)


def break_check(evaluator, base_scope, element_scope):
    reachable = REACHABLE
    if isinstance(element_scope, Flow):
        if element_scope.command == 'if' and element_scope.inputs:
            result = evaluator.eval_statement(element_scope.inputs[0])
            print(result)

    if base_scope != element_scope.parent:
        return reachable & break_check(base_scope, element_scope.parent)
    return UNSURE
