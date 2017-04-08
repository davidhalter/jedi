from jedi.parser.python.tree import PythonLeaf
_IGNORE_EXECUTE_NODES = set([
    'suite', 'subscriptlist', 'subscript', 'simple_stmt', 'sliceop',
    'testlist_comp', 'dictorsetmaker', 'trailer', 'decorators',
    'decorated', 'arglist', 'argument', 'exprlist', 'testlist',
    'testlist_safe', 'testlist1', 'global_stmt', 'file_input', 'for_stmt',
    'while_stmt', 'if_stmt', 'try_stmt', 'with_stmt', 'comp_for', 'comp_if',
    'param', 'except_clause', 'dotted_name', 'keyword_stmt', 'return_stmt',
    'del_stmt', 'pass_stmt', 'nonlocal_stmt', 'assert_stmt', 'break_stmt',
    'continue_stmt', 'raise_stmt', 'yield_stmt'
])

return_ = 'import_name', 'import_from'


# last added: Flow, KeywordStatement


def get_executable_nodes(node, last_added=False):
    """
    For static analysis.
    """
    result = []
    typ = node.type
    if typ == 'classdef':
        # Yield itself, class needs to be executed for decorator checks.
        result.append(node)
        # Super arguments.
        arglist = node.get_super_arglist()
        try:
            children = arglist.children
        except AttributeError:
            if arglist is not None:
                result += get_executable_nodes(arglist)
        else:
            for argument in children:
                if argument.type == 'argument':
                    # metaclass= or list comprehension or */**
                    raise NotImplementedError('Metaclasses not implemented, yet.')
                else:
                    result += get_executable_nodes(argument)

        # Care for the class suite:
        suite = node.children[-1]
        result += get_executable_nodes(suite)
    elif typ == 'yield_expr':
        if len(node.children) > 1:
            # TODO delete?
            result += get_executable_nodes(node.children[1])
    elif typ == 'name':
        next_leaf = node.get_next_leaf()
        if last_added is False and node.parent.type != 'param' and next_leaf != '=':
            result.append(node)
    elif typ == 'expr_stmt':
        # I think evaluating the statement (and possibly returned arrays),
        # should be enough for static analysis.
        result.append(node)
        for child in node.children:
            result += get_executable_nodes(child, last_added=True)
    elif isinstance(node, PythonLeaf):
        pass
    elif typ == 'decorator':
        # decorator
        if node.children[-2] == ')':
            node = children[-3]
            if node != '(':
                result += get_executable_nodes(node)
    else:
        if node.type not in _IGNORE_EXECUTE_NODES and not last_added:
            result.append(node)
            #last_added = True

        for child in node.children:
            result += get_executable_nodes(child, last_added)

    return result
