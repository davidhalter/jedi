from jedi.parser.python import tree

_EXECUTE_NODES = set([
    'funcdef', 'classdef', 'import_from', 'import_name', 'test', 'or_test',
    'and_test', 'not_test', 'comparison', 'expr', 'xor_expr', 'and_expr',
    'shift_expr', 'arith_expr', 'atom_expr', 'term', 'factor', 'power', 'atom'
])

_FLOW_KEYWORDS = (
    'try', 'except', 'finally', 'else', 'if', 'elif', 'with', 'for', 'while'
)


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


def for_stmt_defines_one_name(for_stmt):
    """
    Returns True if only one name is returned: ``for x in y``.
    Returns False if the for loop is more complicated: ``for x, z in y``.

    :returns: bool
    """
    return for_stmt.children[1].type == 'name'


def get_flow_branch_keyword(flow_node, node):
    start_pos = node.start_pos
    if not (flow_node.start_pos < start_pos <= flow_node.end_pos):
        raise ValueError('The node is not part of the flow.')

    keyword = None
    for i, child in enumerate(flow_node.children):
        if start_pos < child.start_pos:
            return keyword
        first_leaf = child.get_first_leaf()
        if first_leaf in _FLOW_KEYWORDS:
            keyword = first_leaf
    return 0
