import re

import parsing
import evaluate
import modules
import debug

__all__ = ['complete', 'goto', 'get_completion_parts', 'set_debug_function']


class NotFoundError(Exception):
    """ A custom error to avoid catching the wrong errors """
    pass


class Completion(object):
    def __init__(self, name, needs_dot, like_name_length):
        self.name = name
        self.needs_dot = needs_dot
        self.like_name_length = like_name_length

    @property
    def complete(self):
        dot = '.' if self.needs_dot else ''
        return dot + self.name.names[-1][self.like_name_length:]

    @property
    def description(self):
        return str(self.name.parent)

    @property
    def help(self):
        try:
            return str(self.name.parent.docstr)
        except:
            return ''

    def get_type(self):
        return type(self.name.parent)

    def get_vim_type(self):
        """
        This is the only function, which is vim specific, it returns the vim
        type, see help(complete-items)
        """
        typ = self.get_type()
        if typ == parsing.Statement:
            return 'v'  # variable
        elif typ == parsing.Function:
            return 'f'  # function / method
        elif typ in [parsing.Class, evaluate.Instance]:
            return 't'  # typedef -> abused as class
        elif typ == parsing.Import:
            return 'd'  # define -> abused as import
        if typ == parsing.Param:
            return 'm'  # member -> abused as param
        else:
            debug.dbg('other python type: ', typ)

        return ''

    def __str__(self):
        return self.name.names[-1]


def get_completion_parts(path):
    """
    Returns the parts for the completion
    :return: tuple - (path, dot, like)
    """
    match = re.match(r'^(.*?)(\.|)(\w?[\w\d]*)$', path, flags=re.S)
    return match.groups()


def complete(source, row, column, source_path):
    """
    An auto completer for python files.

    :param source: The source code of the current file
    :type source: string
    :param row: The row to complete in.
    :type row: int
    :param col: The column to complete in.
    :type col: int
    :param source_path: The path in the os, the current module is in.
    :type source_path: int

    :return: list of completion objects
    :rtype: list
    """
    f = modules.ModuleWithCursor(source_path, source=source, row=row)
    scope = f.parser.user_scope
    path = f.get_path_until_cursor(column)
    debug.dbg('completion_start: %s in %s' % (path, scope))

    # just parse one statement, take it and evaluate it
    path, dot, like = get_completion_parts(path)
    r = parsing.PyFuzzyParser(path, source_path)
    try:
        stmt = r.top.statements[0]
    except IndexError:
        scope_generator = evaluate.get_names_for_scope(scope)
        completions = []
        for dummy, name_list in scope_generator:
            completions += name_list
        #for c in completions:
        #    if isinstance(, parsing.Function):
        #        print c.parent
    else:
        stmt.line_nr = row
        stmt.indent = column
        stmt.parent = scope
        scopes = evaluate.follow_statement(stmt, scope=scope)

        completions = []
        debug.dbg('possible scopes', scopes)
        for s in scopes:
            # TODO is this reall the right way? just ignore the functions? \
            # do the magic functions first? and then recheck here?
            if not isinstance(s, parsing.Function):
                completions += s.get_defined_names()

    completions = [c for c in completions
                            if c.names[-1].lower().startswith(like.lower())]

    _clear_caches()

    needs_dot = not dot and path
    return [Completion(c, needs_dot, len(like)) for c in set(completions)]


def prepare_goto(source, row, column, source_path, is_like_search):
    f = modules.ModuleWithCursor(source_path, source=source, row=row)
    scope = f.parser.user_scope

    if is_like_search:
        path = f.get_path_until_cursor(column)
        path, dot, like = get_completion_parts(path)
    else:
        path = f.get_path_under_cursor(column)

    debug.dbg('start: %s in %s' % (path, scope))

    # just parse one statement, take it and evaluate it
    r = parsing.PyFuzzyParser(path, source_path)
    try:
        stmt = r.top.statements[0]
    except IndexError:
        raise NotFoundError()
    else:
        stmt.line_nr = row
        stmt.indent = column
        stmt.parent = scope
        scopes = evaluate.follow_statement(stmt, scope=scope)
    return scope, scopes


def goto(source, row, column, source_path):
    dummy, scopes = prepare_goto(source, row, column, source_path, False)

    _clear_caches()
    return scopes


def set_debug_function(func_cb):
    """
    You can define a callback debug function to get all the debug messages.
    :param func_cb: The callback function for debug messages, with n params.
    """
    debug.debug_function = func_cb


def _clear_caches():
    evaluate.clear_caches()
