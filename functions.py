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

__all__ = ['complete', 'goto', 'get_definitions',
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
                    and isinstance( self._completion_parent, funcs):
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


class Definition(object):
    def __init__(self, definition):
        """ The definition of a function """
        self.definition = definition
        self._def_parent = self.definition.parent()  # just here to limit gc

        par = self.definition
        while True:
            if par.parent() is not None:
                par = par.parent()
            else:
                break
        self.module_path = str(par.path)

    def get_name(self):
        try:
            # is a func / class
            return self.definition.name
        except AttributeError:
            try:
                # is an array
                return self.definition.type
            except:
                # is a statement
                return self.definition.get_code()

    @property
    def module_name(self):
        path = self.module_path
        try:
            return path[path.rindex(os.path.sep) + 1:]
        except ValueError:
            return path

    def in_builtin_module(self):
        return not self.module_path.endswith('.py')

    @property
    def line_nr(self):
        return self.definition.start_pos[0]

    @property
    def column(self):
        return self.definition.start_pos[1]

    @property
    def description(self):
        d = self.definition
        if isinstance(d, evaluate.InstanceElement):
            d = d.var
        if isinstance(d, evaluate.parsing.Name):
            d = d.parent()

        if isinstance(d, (evaluate.Class, evaluate.Instance)):
            d = 'class ' + str(d.name)
        elif isinstance(d, (evaluate.Function, evaluate.parsing.Function)):
            d = 'def ' + str(d.name)
        elif isinstance(d, evaluate.parsing.Module):
            p = str(d.path)
            # only show module name
            sep = os.path.sep
            p = re.sub(r'^.*?([\w\d]+)(%s__init__)?.py$' % sep, r'\1', p)
            d = 'module ' + p
        else:
            d = d.get_code().replace('\n', '')
        return d

    def __str__(self):
        if self.module_path[0] == os.path.sep:
            position = '@%s' % (self.line_nr)
        else:
            # no path - is a builtin
            position = ''
        return "%s:%s%s" % (self.module_name, self.get_name(), position)

    def __repr__(self):
        return "<%s %s>" % (self.__class__.__name__, self.definition)


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
        scopes = _prepare_goto(source, pos, source_path, f, path, True)
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
                for c in s.get_defined_names():
                    completions.append((c, s))

    completions = [(c, s) for c, s in completions
                        if settings.case_insensitive_completion
                            and c.names[-1].lower().startswith(like.lower())
                            or c.names[-1].startswith(like)]

    needs_dot = not dot and path
    c = [Completion(c, needs_dot, len(like), s) for c, s in set(completions)]

    _clear_caches()
    return c


def _prepare_goto(source, position, source_path, module, goto_path,
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
        scopes = [imports.ImportPath(user_stmt, is_like_search)]
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


def get_definitions(source, line, column, source_path):
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
    pos = (line, column)
    f = modules.ModuleWithCursor(source_path, source=source, position=pos)
    goto_path = f.get_path_under_cursor()

    scopes = _prepare_goto(source, pos, source_path, f, goto_path)
    _clear_caches()
    return [Definition(s) for s in set(scopes)]


def goto(source, line, column, source_path):
    pos = (line, column)
    f = modules.ModuleWithCursor(source_path, source=source, position=pos)

    goto_path = f.get_path_under_cursor()
    goto_path, dot, search_name = _get_completion_parts(goto_path)

    # define goto path the right way
    if not dot:
        goto_path = search_name
        search_name = None

    scopes = _prepare_goto(source, pos, source_path, f, goto_path)
    if not dot:
        try:
            definitions = [evaluate.statement_path[1]]
        except IndexError:
            definitions = []
            for s in scopes:
                if isinstance(s, imports.ImportPath):
                    s = s.follow()[0]
                    try:
                        s = evaluate.statement_path[0]
                    except IndexError:
                        pass
                definitions.append(s)
    else:
        def remove_unreal_imports(names):
            """
            These imports are only virtual, because of multi-line imports.
            """
            new_names = []
            for n in names:
                par = n.parent()
                # This is a special case: If the Import is "virtual" (which
                # means the position is not defined), follow those modules.
                if isinstance(par, parsing.Import) and not par.start_pos[0]:
                    module_count = 0
                    for scope in imports.ImportPath(par).follow():
                        if isinstance(scope, parsing.Import):
                            temp = scope.get_defined_names()
                            new_names += remove_unreal_imports(temp)
                        elif isinstance(scope, parsing.Module) \
                                                        and not module_count:
                            # only first module (others are star imports)
                            module_count += 1
                            new_names.append(scope.get_module_name(n.names))
                else:
                    new_names.append(n)
            return new_names

        names = []
        for s in scopes:
            names += s.get_defined_names()
        names = remove_unreal_imports(names)
        definitions = [n for n in names if n.names[-1] == search_name]
    _clear_caches()
    return [Definition(d) for d in set(definitions)]


def set_debug_function(func_cb):
    """
    You can define a callback debug function to get all the debug messages.
    :param func_cb: The callback function for debug messages, with n params.
    """
    debug.debug_function = func_cb


def _clear_caches():
    evaluate.clear_caches()
