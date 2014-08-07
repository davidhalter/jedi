from jedi.parser.representation import Flow


class Status(object):
    lookup_table = {}

    def __init__(self, value, name):
        self._value = value
        self._name = name
        Status.lookup_table[value] = self

    def invert(self):
        if self is REACHABLE:
            return UNREACHABLE
        elif self is UNREACHABLE:
            return REACHABLE
        else:
            return UNSURE

    def __and__(self, other):
        if UNSURE in (self, other):
            return UNSURE
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
        check_scope = element_scope
        invert = False
        if check_scope.command == 'else':
            check_scope = check_scope.previous
            invert = True

        if check_scope.command == 'if' and check_scope.inputs:
            types = evaluator.eval_statement(check_scope.inputs[0])
            values = set(x.py__bool__() for x in types)
            if len(values) == 1:
                reachable = Status.lookup_table[values.pop()]
                if invert:
                    reachable = reachable.invert()
                if reachable is UNREACHABLE:
                    return UNREACHABLE
            else:
                return UNSURE
        elif check_scope.command in ('try', 'except', 'finally'):
            reachable = UNSURE

    if base_scope != element_scope and base_scope != check_scope.parent:
        return reachable & break_check(evaluator, base_scope, element_scope.parent)
    return reachable
