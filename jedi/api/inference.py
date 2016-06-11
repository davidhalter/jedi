"""
This module has helpers for doing type inference on strings. It is needed,
because we still want to infer types where the syntax is invalid.
"""
from jedi import debug
from jedi.parser import Parser, ParseError
from jedi.evaluate.cache import memoize_default
from jedi.api import helpers


def goto_checks(evaluator, parser, user_context, position, dotted_path, follow_types=False):
    module = evaluator.wrap(parser.module())
    stack = helpers.get_stack_at_position(evaluator.grammar, self._source, module, position)
    stack

def type_inference(evaluator, parser, user_context, position, dotted_path):
    """
    Base for completions/goto. Basically it returns the resolved scopes
    under cursor.
    """
    debug.dbg('start: %s in %s', dotted_path, parser.user_scope())

    # Just parse one statement, take it and evaluate it.
    eval_stmt = get_under_cursor_stmt(evaluator, parser, dotted_path, position)
    if eval_stmt is None:
        return []

    return evaluator.eval_element(eval_stmt)


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
