from jedi.parser.representation import Flow


class Status(object):
    lookup_table = {}

    def __init__(self, value, name):
        self._value = value
        self._name = name
        Status.lookup_table[value] = self

    def __eq__(self, other):
        return self._value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __and__(self, other):
        if UNSURE in (self, other):
            return other
        else:
            return REACHABLE if self._value and other._value else UNREACHABLE

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self._name)


REACHABLE = Status(True, 'reachable')
UNREACHABLE = Status(False, 'unreachable')
UNSURE = Status(None, 'unsure')


def break_check(evaluator, base_scope, element_scope):
    reachable = REACHABLE
    if isinstance(element_scope, Flow):
        if element_scope.command == 'if' and element_scope.inputs:
            types = evaluator.eval_statement(element_scope.inputs[0])
            values = set(x.py__bool__() for x in types)
            if len(values) == 1:
                reachable = Status.lookup_table[values.pop()]
            else:
                return UNSURE

    if base_scope != element_scope and base_scope != element_scope.parent:
        return reachable & break_check(evaluator, base_scope, element_scope.parent)
    return reachable
