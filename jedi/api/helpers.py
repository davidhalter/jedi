"""
Helpers for the API
"""
import re

from jedi import debug
from jedi.evaluate import helpers
from jedi.evaluate import imports
from jedi.parser import representation as pr


def func_call_and_param_index(user_stmt, position):
    debug.speed('func_call start')
    call, index = None, 0
    if call is None:
        if user_stmt is not None and isinstance(user_stmt, pr.Statement):
            call, index, _ = helpers.search_call_signatures(user_stmt, position)
    debug.speed('func_call parsed')
    return call, index


def completion_parts(path_until_cursor):
    """
    Returns the parts for the completion
    :return: tuple - (path, dot, like)
    """
    match = re.match(r'^(.*?)(\.|)(\w?[\w\d]*)$', path_until_cursor, flags=re.S)
    return match.groups()


def sorted_definitions(defs):
    # Note: `or ''` below is required because `module_path` could be
    return sorted(defs, key=lambda x: (x.module_path or '', x.line or 0, x.column or 0))


def get_on_import_stmt(evaluator, user_context, user_stmt, is_like_search=False):
    """
    Resolve the user statement, if it is an import. Only resolve the
    parts until the user position.
    """
    import_names = user_stmt.get_all_import_names()
    kill_count = -1
    cur_name_part = None
    for i in import_names:
        if user_stmt.alias == i:
            continue
        for name_part in i.names:
            if name_part.end_pos >= user_context.position:
                if not cur_name_part:
                    cur_name_part = name_part
                kill_count += 1

    context = user_context.get_context()
    just_from = next(context) == 'from'

    i = imports.ImportPath(evaluator, user_stmt, is_like_search,
                           kill_count=kill_count, direct_resolve=True,
                           is_just_from=just_from)
    return i, cur_name_part
