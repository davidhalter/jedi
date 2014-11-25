"""
Helpers for the API
"""
import re

from jedi.evaluate import imports


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
    name = user_stmt.name_for_position(user_context.position)
    if name is None:
        raise NotImplementedError

    i = imports.ImportWrapper(evaluator, name)
    return i, name


def check_error_statements(evaluator, module, pos):
    for error_statement in module.error_statement_stacks:
        if error_statement.first_type in ('import_from' or 'import_name') \
                and error_statement.first_pos < pos <= error_statement.next_start_pos:
            return importer_from_error_statement(evaluator, module, error_statement, pos)
    return None


def importer_from_error_statement(evaluator, module, error_statement, pos):
    names = []
    level = 0
    for typ, nodes in error_statement.stack:
        if typ == 'dotted_name':
            names += nodes[::2]

    return imports.get_importer(evaluator, names, module, level)
