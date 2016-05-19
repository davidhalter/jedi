"""
This module has helpers for doing type inference on strings. It is needed,
because we still want to infer types where the syntax is invalid.
"""
from jedi.parser import Parser, ParseError
from jedi.evaluate.cache import memoize_default


def type_inference(evaluator, parser, user_context, position, dotted_path, is_completion=False):
    pass


@memoize_default(evaluator_is_first_arg=True)
def get_under_cursor_stmt(evaluator, parser, cursor_txt, start_pos):
    """
    Create a syntax tree node from a string under the cursor. Directly taking
    the node under the cursor (of the actual syntax tree) would disallow
    invalid code to be understood.

    The start_pos is typically the position of the current cursor, which may
    not be the real starting position of that node, but it works perfectly well
    (for both completions in docstrings and statements).
    """
    try:
        stmt = Parser(evaluator.grammar, cursor_txt, 'eval_input').get_parsed_node()
    except ParseError:
        return None

    user_stmt = parser.user_stmt()
    if user_stmt is None:
        pos = start_pos
    else:
        pos = user_stmt.start_pos

    stmt.move(pos[0] - 1, pos[1])  # Moving the offset.
    stmt.parent = parser.user_scope()
    return stmt
