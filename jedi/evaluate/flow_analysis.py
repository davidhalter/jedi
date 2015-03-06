from jedi.parser import tree as pr


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


def break_check(evaluator, base_scope, stmt, origin_scope=None):
    from jedi.evaluate.representation import wrap
    element_scope = wrap(evaluator, stmt.get_parent_scope(include_flows=True))
    # Direct parents get resolved, we filter scopes that are separate branches.
    # This makes sense for autocompletion and static analysis. For actual
    # Python it doesn't matter, because we're talking about potentially
    # unreachable code.
    # e.g. `if 0:` would cause all name lookup within the flow make
    # unaccessible. This is not a "problem" in Python, because the code is
    # never called. In Jedi though, we still want to infer types.
    while origin_scope is not None:
        if element_scope == origin_scope:
            return REACHABLE
        origin_scope = origin_scope.parent
    return _break_check(evaluator, stmt, base_scope, element_scope)


def _break_check(evaluator, stmt, base_scope, element_scope):
    from jedi.evaluate.representation import wrap
    element_scope = wrap(evaluator, element_scope)
    base_scope = wrap(evaluator, base_scope)

    reachable = REACHABLE
    if isinstance(element_scope, pr.IfStmt):
        if element_scope.node_after_else(stmt):
            for check_node in element_scope.check_nodes():
                reachable = _check_if(evaluator, check_node)
                if reachable in (REACHABLE, UNSURE):
                    break
            reachable = reachable.invert()
        else:
            node = element_scope.node_in_which_check_node(stmt)
            reachable = _check_if(evaluator, node)
    elif isinstance(element_scope, (pr.TryStmt, pr.WhileStmt)):
        return UNSURE

    # Only reachable branches need to be examined further.
    if reachable in (UNREACHABLE, UNSURE):
        return reachable

    if base_scope != element_scope and base_scope != element_scope.parent:
        return reachable & _break_check(evaluator, stmt, base_scope, element_scope.parent)
    return reachable


def _check_if(evaluator, node):
    types = evaluator.eval_element(node)
    values = set(x.py__bool__() for x in types)
    if len(values) == 1:
        return Status.lookup_table[values.pop()]
    else:
        return UNSURE
