from jedi.parser.python import tree

_EXECUTE_NODES = set([
    'funcdef', 'classdef', 'import_from', 'import_name', 'test', 'or_test',
    'and_test', 'not_test', 'comparison', 'expr', 'xor_expr', 'and_expr',
    'shift_expr', 'arith_expr', 'atom_expr', 'term', 'factor', 'power', 'atom'
])

return_ = 'import_name', 'import_from'


# last added: Flow, KeywordStatement


def get_executable_nodes(node, last_added=False):
    """
    For static analysis.
    """
    result = []
    typ = node.type
    if typ == 'name':
        next_leaf = node.get_next_leaf()
        if last_added is False and node.parent.type != 'param' and next_leaf != '=':
            result.append(node)
    elif typ == 'expr_stmt':
        # I think evaluating the statement (and possibly returned arrays),
        # should be enough for static analysis.
        result.append(node)
        for child in node.children:
            result += get_executable_nodes(child, last_added=True)
    elif typ == 'decorator':
        # decorator
        if node.children[-2] == ')':
            node = node.children[-3]
            if node != '(':
                result += get_executable_nodes(node)
    else:
        try:
            children = node.children
        except AttributeError:
            pass
        else:
            if node.type in _EXECUTE_NODES and not last_added:
                result.append(node)

            for child in children:
                result += get_executable_nodes(child, last_added)

    return result


def get_comp_fors(comp_for):
    yield comp_for
    last = comp_for.children[-1]
    while True:
        if last.type == 'comp_for':
            yield last
        elif not last.type == 'comp_if':
            break
        last = last.children[-1]
