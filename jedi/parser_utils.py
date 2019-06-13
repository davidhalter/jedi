import re
import textwrap
from inspect import cleandoc

from parso.python import tree
from parso.cache import parser_cache

from jedi._compatibility import literal_eval, force_unicode

_EXECUTE_NODES = {'funcdef', 'classdef', 'import_from', 'import_name', 'test',
                  'or_test', 'and_test', 'not_test', 'comparison', 'expr',
                  'xor_expr', 'and_expr', 'shift_expr', 'arith_expr',
                  'atom_expr', 'term', 'factor', 'power', 'atom'}

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


def get_sync_comp_fors(comp_for):
    yield comp_for
    last = comp_for.children[-1]
    while True:
        if last.type == 'comp_for':
            yield last.children[1]  # Ignore the async.
        elif last.type == 'sync_comp_for':
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


def get_statement_of_position(node, pos):
    for c in node.children:
        if c.start_pos <= pos <= c.end_pos:
            if c.type not in ('decorated', 'simple_stmt', 'suite',
                              'async_stmt', 'async_funcdef') \
                    and not isinstance(c, (tree.Flow, tree.ClassOrFunc)):
                return c
            else:
                try:
                    return get_statement_of_position(c, pos)
                except AttributeError:
                    pass  # Must be a non-scope
    return None


def clean_scope_docstring(scope_node):
    """ Returns a cleaned version of the docstring token. """
    node = scope_node.get_doc_node()
    if node is not None:
        # TODO We have to check next leaves until there are no new
        # leaves anymore that might be part of the docstring. A
        # docstring can also look like this: ``'foo' 'bar'
        # Returns a literal cleaned version of the ``Token``.
        cleaned = cleandoc(safe_literal_eval(node.value))
        # Since we want the docstr output to be always unicode, just
        # force it.
        return force_unicode(cleaned)
    return ''


def safe_literal_eval(value):
    first_two = value[:2].lower()
    if first_two[0] == 'f' or first_two in ('fr', 'rf'):
        # literal_eval is not able to resovle f literals. We have to do that
        # manually, but that's right now not implemented.
        return ''

    try:
        return literal_eval(value)
    except SyntaxError:
        # It's possible to create syntax errors with literals like rb'' in
        # Python 2. This should not be possible and in that case just return an
        # empty string.
        # Before Python 3.3 there was a more strict definition in which order
        # you could define literals.
        return ''


def get_call_signature(funcdef, width=72, call_string=None,
                       omit_first_param=False, omit_return_annotation=False):
    """
    Generate call signature of this function.

    :param width: Fold lines if a line is longer than this value.
    :type width: int
    :arg func_name: Override function name when given.
    :type func_name: str

    :rtype: str
    """
    # Lambdas have no name.
    if call_string is None:
        if funcdef.type == 'lambdef':
            call_string = '<lambda>'
        else:
            call_string = funcdef.name.value
    params = funcdef.get_params()
    if omit_first_param:
        params = params[1:]
    p = '(' + ''.join(param.get_code() for param in params).strip() + ')'
    # TODO this is pretty bad, we should probably just normalize.
    p = re.sub(r'\s+', ' ', p)
    if funcdef.annotation and not omit_return_annotation:
        rtype = " ->" + funcdef.annotation.get_code()
    else:
        rtype = ""
    code = call_string + p + rtype

    return '\n'.join(textwrap.wrap(code, width))


def move(node, line_offset):
    """
    Move the `Node` start_pos.
    """
    try:
        children = node.children
    except AttributeError:
        node.line += line_offset
    else:
        for c in children:
            move(c, line_offset)


def get_following_comment_same_line(node):
    """
    returns (as string) any comment that appears on the same line,
    after the node, including the #
    """
    try:
        if node.type == 'for_stmt':
            whitespace = node.children[5].get_first_leaf().prefix
        elif node.type == 'with_stmt':
            whitespace = node.children[3].get_first_leaf().prefix
        elif node.type == 'funcdef':
            # actually on the next line
            whitespace = node.children[4].get_first_leaf().get_next_leaf().prefix
        else:
            whitespace = node.get_last_leaf().get_next_leaf().prefix
    except AttributeError:
        return None
    except ValueError:
        # TODO in some particular cases, the tree doesn't seem to be linked
        # correctly
        return None
    if "#" not in whitespace:
        return None
    comment = whitespace[whitespace.index("#"):]
    if "\r" in comment:
        comment = comment[:comment.index("\r")]
    if "\n" in comment:
        comment = comment[:comment.index("\n")]
    return comment


def is_scope(node):
    t = node.type
    if t == 'comp_for':
        # Starting with Python 3.8, async is outside of the statement.
        return node.children[1].type != 'sync_comp_for'

    return t in ('file_input', 'classdef', 'funcdef', 'lambdef', 'sync_comp_for')


def get_parent_scope(node, include_flows=False):
    """
    Returns the underlying scope.
    """
    scope = node.parent
    if scope is None:
        return None  # It's a module already.

    while True:
        if is_scope(scope) or include_flows and isinstance(scope, tree.Flow):
            if scope.type in ('classdef', 'funcdef', 'lambdef'):
                index = scope.children.index(':')
                if scope.children[index].start_pos >= node.start_pos:
                    if node.parent.type == 'param' and node.parent.name == node:
                        pass
                    elif node.parent.type == 'tfpdef' and node.parent.children[0] == node:
                        pass
                    else:
                        scope = scope.parent
                        continue
            return scope
        scope = scope.parent
    return scope


def get_cached_code_lines(grammar, path):
    """
    Basically access the cached code lines in parso. This is not the nicest way
    to do this, but we avoid splitting all the lines again.
    """
    return parser_cache[grammar._hashed][path].lines
