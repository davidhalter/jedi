import re
import weakref
import os

import parsing
import dynamic  # must be before evaluate, because it needs to be loaded first.
import evaluate
import modules
import debug
import imports
import settings
import keywords

from _compatibility import next

__all__ = ['complete', 'goto', 'get_definition', 'related_names',
           'NotFoundError', 'set_debug_function']


class NotFoundError(Exception):
    """ A custom error to avoid catching the wrong exceptions """
    pass


class Completion(object):
    def __init__(self, name, needs_dot, like_name_length, base):
        self.name = name
        self.needs_dot = needs_dot
        self.like_name_length = like_name_length
        self._completion_parent = name.parent()  # limit gc
        self.base = base

    @property
    def complete(self):
        dot = '.' if self.needs_dot else ''
        append = ''
        funcs = (parsing.Function, evaluate.Function)
        if settings.add_bracket_after_function \
                    and isinstance(self._completion_parent, funcs):
            append = '('

        if settings.add_dot_after_module:
            if isinstance(self.base, parsing.Module):
                append += '.'
        return dot + self.name.names[-1][self.like_name_length:] + append

    @property
    def word(self):
        return str(self.name.names[-1])

    @property
    def description(self):
        return str(self.name.parent())

    @property
    def doc(self):
        try:
            return str(self.name.parent().docstr)
        except AttributeError:
            return ''

    def get_type(self):
        return type(self.name.parent())

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.name)


class Definition(dynamic.BaseOutput):
    def __init__(self, definition):
        """ The definition of a function """
        super(Definition, self).__init__(definition.start_pos, definition)
        self._def_parent = definition.parent()  # just here to limit gc

    @property
    def description(self):
        d = self.definition
        if isinstance(d, evaluate.InstanceElement):
            d = d.var
        if isinstance(d, evaluate.parsing.Name):
            d = d.parent()

        if isinstance(d, evaluate.Array):
            d = 'class ' + d.type
        elif isinstance(d, (parsing.Class, evaluate.Class, evaluate.Instance)):
            d = 'class ' + str(d.name)
        elif isinstance(d, (evaluate.Function, evaluate.parsing.Function)):
            d = 'def ' + str(d.name)
        elif isinstance(d, evaluate.parsing.Module):
            # only show module name
            d = 'module %s' % self.module_name
        elif isinstance(d, keywords.Keyword):
            d = 'keyword %s' % d.name
        else:
            d = d.get_code().replace('\n', '')
        return d

    @property
    def doc(self):
        try:
            return str(self.definition.docstr)
        except AttributeError:
            return ''

    @property
    def desc_with_module(self):
        if self.module_path.endswith('.py') \
                    and not isinstance(self.definition, parsing.Module):
            position = '@%s' % (self.line_nr)
        else:
            # is a builtin or module
            position = ''
        return "%s:%s%s" % (self.module_name, self.description, position)


def _get_completion_parts(path):
    """
    Returns the parts for the completion
    :return: tuple - (path, dot, like)
    """
    match = re.match(r'^(.*?)(\.|)(\w?[\w\d]*)$', path, flags=re.S)
    return match.groups()


def complete(source, line, column, source_path):
    """
    An auto completer for python files.

    :param source: The source code of the current file
    :type source: string
    :param line: The line to complete in.
    :type line: int
    :param col: The column to complete in.
    :type col: int
    :param source_path: The path in the os, the current module is in.
    :type source_path: str

    :return: list of Completion objects.
    :rtype: list
    """
    pos = (line, column)
    f = modules.ModuleWithCursor(source_path, source=source, position=pos)
    path = f.get_path_until_cursor()
    path, dot, like = _get_completion_parts(path)

    try:
        scopes = _prepare_goto(pos, source_path, f, path, True)
    except NotFoundError:
        scope_generator = evaluate.get_names_for_scope(f.parser.user_scope,
                                                                        pos)
        completions = []
        for scope, name_list in scope_generator:
            for c in name_list:
                completions.append((c, scope))
    else:
        completions = []
        debug.dbg('possible scopes', scopes)
        for s in scopes:
            # TODO is this really the right way? just ignore the functions? \
            # do the magic functions first? and then recheck here?
            if not isinstance(s, evaluate.Function):
                if isinstance(s, imports.ImportPath):
                    names = s.get_defined_names(on_import_stmt=True)
                else:
                    names = s.get_defined_names()
                for c in names:
                    completions.append((c, s))

    completions = [(c, s) for c, s in completions
                        if settings.case_insensitive_completion
                            and c.names[-1].lower().startswith(like.lower())
                            or c.names[-1].startswith(like)]

    needs_dot = not dot and path
    c = [Completion(c, needs_dot, len(like), s) for c, s in set(completions)]

    _clear_caches()
    return c


def _prepare_goto(position, source_path, module, goto_path,
                                                        is_like_search=False):
    scope = module.parser.user_scope
    debug.dbg('start: %s in %s' % (goto_path, scope))

    user_stmt = module.parser.user_stmt
    if not user_stmt and len(goto_path.split('\n')) > 1:
        # If the user_stmt is not defined and the goto_path is multi line,
        # something's strange. Most probably the backwards tokenizer matched to
        # much.
        return []

    if isinstance(user_stmt, parsing.Import):
        import_names = user_stmt.get_all_import_names()
        count = 0
        kill_count = -1
        for i in import_names:
            for name_part in i.names:
                count += 1
                if position <= name_part.end_pos:
                    kill_count += 1
        scopes = [imports.ImportPath(user_stmt, is_like_search,
                        kill_count=kill_count, direct_resolve=True)]
    else:
        # just parse one statement, take it and evaluate it
        r = parsing.PyFuzzyParser(goto_path, source_path, no_docstr=True)
        try:
            stmt = r.module.statements[0]
        except IndexError:
            raise NotFoundError()

        stmt.start_pos = position
        stmt.parent = weakref.ref(scope)
        scopes = evaluate.follow_statement(stmt)
    return scopes


def get_definition(source, line, column, source_path):
    """
    Returns the definitions of a the path under the cursor.
    This is not a goto function! This follows complicated paths and returns the
    end, not the first definition.

    :param source: The source code of the current file
    :type source: string
    :param line: The line to complete in.
    :type line: int
    :param col: The column to complete in.
    :type col: int
    :param source_path: The path in the os, the current module is in.
    :type source_path: int

    :return: list of Definition objects, which are basically scopes.
    :rtype: list
    """
    def resolve_import_paths(scopes):
        for s in scopes.copy():
            if isinstance(s, imports.ImportPath):
                scopes.remove(s)
                scopes.update(resolve_import_paths(set(s.follow())))
        return scopes

    pos = (line, column)
    f = modules.ModuleWithCursor(source_path, source=source, position=pos)
    goto_path = f.get_path_under_cursor()

    context = f.get_context()
    if next(context) in ('class', 'def'):
        scopes = set([f.parser.user_scope])
    elif not goto_path:
        op = f.get_operator_under_cursor()
        scopes = set([keywords.get_operator(op, pos)] if op else [])
    else:
        scopes = set(_prepare_goto(pos, source_path, f, goto_path))

    scopes = resolve_import_paths(scopes)

    # add keywords
    scopes |= keywords.get_keywords(string=goto_path, pos=pos)

    d = set([Definition(s) for s in scopes])
    _clear_caches()
    return sorted(d, key=lambda x: (x.module_path, x.start_pos))


def goto(source, line, column, source_path):
    pos = (line, column)
    f = modules.ModuleWithCursor(source_path, source=source, position=pos)

    goto_path = f.get_path_under_cursor()
    goto_path, dot, search_name = _get_completion_parts(goto_path)

    # define goto path the right way
    if not dot:
        goto_path = search_name
        search_name_new = None
    else:
        search_name_new = search_name

    context = f.get_context()
    if next(context) in ('class', 'def'):
        definitions = set([f.parser.user_scope])
    else:
        scopes = _prepare_goto(pos, source_path, f, goto_path)
        definitions = evaluate.goto(scopes, search_name_new)

    d = [Definition(d) for d in set(definitions)]
    _clear_caches()
    return sorted(d, key=lambda x: (x.module_path, x.start_pos))


def related_names(source, line, column, source_path):
    """
    Returns `dynamic.RelatedName` objects, which contain all names, that are
    defined by the same variable, function, class or import.
    This function can be used either to show all the usages of a variable or
    for renaming purposes.
    """
    pos = (line, column)
    f = modules.ModuleWithCursor(source_path, source=source, position=pos)

    goto_path = f.get_path_under_cursor()
    goto_path, dot, search_name = _get_completion_parts(goto_path)

    # define goto path the right way
    if not dot:
        goto_path = search_name
        search_name_new = None
    else:
        search_name_new = search_name

    context = f.get_context()
    if next(context) in ('class', 'def'):
        if isinstance(f.parser.user_scope, parsing.Function):
            e = evaluate.Function(f.parser.user_scope)
        else:
            e = evaluate.Class(f.parser.user_scope)
        definitions = [e]
    elif isinstance(f.parser.user_stmt, (parsing.Param, parsing.Import)):
        definitions = [f.parser.user_stmt]
    else:
        scopes = _prepare_goto(pos, source_path, f, goto_path)
        definitions = evaluate.goto(scopes, search_name_new)

    module = set([d.get_parent_until() for d in definitions])
    module.add(f.parser.module)
    names = dynamic.related_names(definitions, search_name, module)

    for d in definitions:
        if isinstance(d, parsing.Statement):
            def add_array(arr):
                calls = dynamic._scan_array(arr, search_name)
                for call in calls:
                    for n in call.name.names:
                        if n == search_name:
                            names.append(dynamic.RelatedName(n, d))
            for op, arr in d.assignment_details:
                add_array(arr)
            if not d.assignment_details:
                add_array(d.get_assignment_calls())
        elif isinstance(d, parsing.Import):
            is_user = d == f.parser.user_stmt
            check_names = [d.namespace, d.alias, d.from_ns] if is_user \
                                                    else d.get_defined_names()
            for name in check_names:
                if name:
                    for n in name.names:
                        if n.start_pos <= pos <= n.end_pos or not is_user:
                            names.append(dynamic.RelatedName(n, d))
        elif isinstance(d, parsing.Name):
            names.append(dynamic.RelatedName(d.names[0], d))
        else:
            names.append(dynamic.RelatedName(d.name.names[0], d))

    _clear_caches()
    return sorted(names, key=lambda x: (x.module_path, x.start_pos))


def set_debug_function(func_cb):
    """
    You can define a callback debug function to get all the debug messages.
    :param func_cb: The callback function for debug messages, with n params.
    """
    debug.debug_function = func_cb


def _clear_caches():
    evaluate.clear_caches()
