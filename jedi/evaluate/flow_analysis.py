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
        if element_scope.command == 'else':
            check_scope = element_scope
            while check_scope.previous is not None:
                check_scope = check_scope.previous
                reachable = _check_flow(evaluator, check_scope)
                if reachable in (REACHABLE, UNSURE):
                    break
            reachable = reachable.invert()
        else:
            reachable = _check_flow(evaluator, element_scope)

    # Only reachable branches need to be examined further.
    if reachable in (UNREACHABLE, UNSURE):
        return reachable

    if base_scope != element_scope and base_scope != element_scope.parent:
        return reachable & break_check(evaluator, base_scope, element_scope.parent)
    return reachable


def _check_flow(evaluator, flow):
    if flow.command in ('elif', 'if') and flow.inputs:
        types = evaluator.eval_statement(flow.inputs[0])
        values = set(x.py__bool__() for x in types)
        if len(values) == 1:
            return Status.lookup_table[values.pop()]
        else:
            return UNSURE
    elif flow.command in ('try', 'except', 'finally', 'while'):
        return UNSURE
    else:  # for loop
        return REACHABLE
