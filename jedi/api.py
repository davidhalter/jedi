"""
Jedi is an autocompletion library for Python. It offers additonal
services such as goto / get_definition / pydoc support /
get_in_function_call / related names.

To give you a simple exmple how you can use the jedi library,
here is an exmple for the autocompletion feature:

>>> import jedi
>>> source = '''import json; json.l'''
>>> script = jedi.Script(source, 1, 19, '')
>>> script
<jedi.api.Script at 0x7f6d40f3db90>
>>> completions = script.complete()
>>> completions
[<Completion: load>, <Completion: loads>]
>>> completions[0].complete
'oad'
>>> completions[0].word
'load'

As you see Jedi is pretty simple and allows you to concentrate
writing a good text editor, while still having very good IDE features
for Python.
"""
from __future__ import with_statement
__all__ = ['Script', 'NotFoundError', 'set_debug_function']

import re

import parsing
import dynamic
import imports
import evaluate
import modules
import debug
import settings
import keywords
import helpers
import builtin
import api_classes

from _compatibility import next, unicode


class NotFoundError(Exception):
    """ A custom error to avoid catching the wrong exceptions """
    pass


class Script(object):
    """
    A Script is the base for a completion, goto or whatever call.

    :param source: The source code of the current file
    :type source: string
    :param line: The line to complete in.
    :type line: int
    :param col: The column to complete in.
    :type col: int
    :param source_path: The path in the os, the current module is in.
    :type source_path: string or None
    :param source_encoding: encoding for decoding `source`, when it
                            is not a `unicode` object.
    :type source_encoding: string
    """
    def __init__(self, source, line, column, source_path,
                 source_encoding='utf-8'):
        debug.reset_time()
        try:
            source = unicode(source, source_encoding, 'replace')
            # Use 'replace' over 'ignore' to hold code structure.
        except TypeError:  # `source` is already a unicode object
            pass
        self.pos = line, column
        self.module = modules.ModuleWithCursor(source_path, source=source,
                                                            position=self.pos)
        self.source_path = source_path
        debug.speed('init')

    @property
    def parser(self):
        """ The lazy parser """
        return self.module.parser

    def complete(self):
        """
        An auto completer for python files.

        :return: list of Completion objects, sorted by name and __ comes last.
        :rtype: list
        """
        def follow_imports_if_possible(name):
            # TODO remove this, or move to another place (not used)
            par = name.parent
            if isinstance(par, parsing.Import) and not \
                        isinstance(self.parser.user_stmt, parsing.Import):
                new = imports.ImportPath(par).follow(is_goto=True)
                # Only remove the old entry if a new one has been found.
                #print par, new, par.parent
                if new:
                    try:
                        return new
                    except AttributeError:  # .name undefined
                        pass
            return [name]


        debug.speed('complete start')
        path = self.module.get_path_until_cursor()
        path, dot, like = self._get_completion_parts(path)

        try:
            scopes = list(self._prepare_goto(path, True))
        except NotFoundError:
            scopes = []
            scope_generator = evaluate.get_names_for_scope(
                                            self.parser.user_scope, self.pos)
            completions = []
            for scope, name_list in scope_generator:
                for c in name_list:
                    completions.append((c, scope))
        else:
            completions = []
            debug.dbg('possible scopes', scopes)
            for s in scopes:
                if s.isinstance(evaluate.Function):
                    names = s.get_magic_method_names()
                else:
                    if isinstance(s, imports.ImportPath):
                        if like == 'import':
                            l = self.module.get_line(self.pos[0])[:self.pos[1]]
                            if not l.endswith('import import'):
                                continue
                        names = s.get_defined_names(on_import_stmt=True)
                    else:
                        names = s.get_defined_names()

                for c in names:
                    completions.append((c, s))

        if not dot:  # named_params have no dots
            call_def = self.get_in_function_call()
            if call_def:
                if not call_def.module.is_builtin():
                    for p in call_def.params:
                        completions.append((p.get_name(), p))

            # Do the completion if there is no path before and no import stmt.
            if (not scopes or not isinstance(scopes[0], imports.ImportPath)) \
                        and not path:
                # add keywords
                bs = builtin.Builtin.scope
                completions += ((k, bs) for k in keywords.get_keywords(
                                                                    all=True))

        needs_dot = not dot and path

        comps = []
        for c, s in set(completions):
            n = c.names[-1]
            if settings.case_insensitive_completion \
                    and n.lower().startswith(like.lower()) \
                    or n.startswith(like):
                if not evaluate.filter_private_variable(s,
                                                    self.parser.user_stmt, n):
                    new = api_classes.Completion(c, needs_dot,
                                                    len(like), s)
                    comps.append(new)

        debug.speed('complete end')

        return sorted(comps, key=lambda x: (x.word.startswith('__'),
                                            x.word.startswith('_'),
                                            x.word.lower()))

    def _prepare_goto(self, goto_path, is_like_search=False):
        """ Base for complete, goto and get_definition. Basically it returns
        the resolved scopes under cursor. """
        debug.dbg('start: %s in %s' % (goto_path, self.parser.scope))

        user_stmt = self.parser.user_stmt
        debug.speed('parsed')
        if not user_stmt and len(goto_path.split('\n')) > 1:
            # If the user_stmt is not defined and the goto_path is multi line,
            # something's strange. Most probably the backwards tokenizer
            # matched to much.
            return []

        if isinstance(user_stmt, parsing.Import):
            scopes = [self._get_on_import_stmt(is_like_search)[0]]
        else:
            # just parse one statement, take it and evaluate it
            stmt = self._get_under_cursor_stmt(goto_path)
            scopes = evaluate.follow_statement(stmt)
        return scopes

    def _get_under_cursor_stmt(self, cursor_txt):
        r = parsing.PyFuzzyParser(cursor_txt, self.source_path, no_docstr=True)
        try:
            stmt = r.module.statements[0]
        except IndexError:
            raise NotFoundError()
        stmt.start_pos = self.pos
        stmt.parent = self.parser.user_scope
        return stmt

    def get_definition(self):
        """
        Returns the definitions of a the path under the cursor. This is
        not a goto function! This follows complicated paths and returns the
        end, not the first definition.
        The big difference of goto and get_definition is that goto doesn't
        follow imports and statements.
        Multiple objects may be returned, because Python itself is a dynamic
        language, which means depending on an option you can have two different
        versions of a function.

        :return: list of Definition objects, which are basically scopes.
        :rtype: list
        """
        def resolve_import_paths(scopes):
            for s in scopes.copy():
                if isinstance(s, imports.ImportPath):
                    scopes.remove(s)
                    scopes.update(resolve_import_paths(set(s.follow())))
            return scopes

        goto_path = self.module.get_path_under_cursor()

        context = self.module.get_context()
        if next(context) in ('class', 'def'):
            scopes = set([self.module.parser.user_scope])
        elif not goto_path:
            op = self.module.get_operator_under_cursor()
            scopes = set([keywords.get_operator(op, self.pos)] if op else [])
        else:
            scopes = set(self._prepare_goto(goto_path))

        scopes = resolve_import_paths(scopes)

        # add keywords
        scopes |= keywords.get_keywords(string=goto_path, pos=self.pos)

        d = set([api_classes.Definition(s) for s in scopes
                    if not isinstance(s, imports.ImportPath._GlobalNamespace)])
        return sorted(d, key=lambda x: (x.module_path, x.start_pos))

    def goto(self):
        """
        Returns the first definition found by goto. This means: It doesn't
        follow imports and statements.
        Multiple objects may be returned, because Python itself is a dynamic
        language, which means depending on an option you can have two different
        versions of a function.

        :return: list of Definition objects, which are basically scopes.
        """
        d = [api_classes.Definition(d) for d in set(self._goto()[0])]
        return sorted(d, key=lambda x: (x.module_path, x.start_pos))

    def _goto(self, add_import_name=False):
        """
        Used for goto and related_names.
        :param add_import_name: TODO add description
        """
        def follow_inexistent_imports(defs):
            """ Imports can be generated, e.g. following
            `multiprocessing.dummy` generates an import dummy in the
            multiprocessing module. The Import doesn't exist -> follow.
            """
            definitions = set(defs)
            for d in defs:
                if isinstance(d.parent, parsing.Import) \
                                        and d.start_pos == (0, 0):
                    i = imports.ImportPath(d.parent).follow(is_goto=True)
                    definitions.remove(d)
                    definitions |= follow_inexistent_imports(i)
            return definitions

        goto_path = self.module.get_path_under_cursor()
        context = self.module.get_context()
        if next(context) in ('class', 'def'):
            user_scope = self.parser.user_scope
            definitions = set([user_scope.name])
            search_name = str(user_scope.name)
        elif isinstance(self.parser.user_stmt, parsing.Import):
            s, name_part = self._get_on_import_stmt()
            try:
                definitions = [s.follow(is_goto=True)[0]]
            except IndexError:
                definitions = []
            search_name = str(name_part)

            if add_import_name:
                import_name = self.parser.user_stmt.get_defined_names()
                # imports have only one name
                if name_part == import_name[0].names[-1]:
                    definitions.append(import_name[0])
        else:
            stmt = self._get_under_cursor_stmt(goto_path)
            defs, search_name = evaluate.goto(stmt)
            definitions = follow_inexistent_imports(defs)
        return definitions, search_name

    def related_names(self, additional_module_paths=[]):
        """
        Returns `dynamic.RelatedName` objects, which contain all names, that
        are defined by the same variable, function, class or import.
        This function can be used either to show all the usages of a variable
        or for renaming purposes.

        TODO implement additional_module_paths
        """
        user_stmt = self.parser.user_stmt
        definitions, search_name = self._goto(add_import_name=True)
        if isinstance(user_stmt, parsing.Statement) \
                    and self.pos < user_stmt.get_assignment_calls().start_pos:
            # the search_name might be before `=`
            definitions = [v for v in user_stmt.set_vars
                                                if str(v) == search_name]
        if not isinstance(user_stmt, parsing.Import):
            # import case is looked at with add_import_name option
            definitions = dynamic.related_name_add_import_modules(definitions,
                                                                search_name)

        module = set([d.get_parent_until() for d in definitions])
        module.add(self.parser.module)
        names = dynamic.related_names(definitions, search_name, module)

        for d in set(definitions):
            if isinstance(d, parsing.Module):
                names.append(api_classes.RelatedName(d, d))
            else:
                names.append(api_classes.RelatedName(d.names[0], d))

        return sorted(set(names), key=lambda x: (x.module_path, x.start_pos),
                                                                reverse=True)

    def get_in_function_call(self):
        """
        Return the function, that the cursor is in, e.g.:
        >>> isinstance(| # | <-- cursor is here

        This would return the `isinstance` function. In contrary:
        >>> isinstance()| # | <-- cursor is here

        This would return `None`.
        """
        def check_user_stmt(user_stmt):
            if user_stmt is None \
                        or not isinstance(user_stmt, parsing.Statement):
                return None, 0
            ass = helpers.fast_parent_copy(user_stmt.get_assignment_calls())

            call, index, stop = helpers.scan_array_for_pos(ass, self.pos)
            return call, index

        def check_cache():
            """ Do the parsing with a part parser, therefore reduce ressource
            costs.
            TODO this is not working with multi-line docstrings, improve.
            """
            if self.source_path is None:
                return None, 0

            try:
                timestamp, parser = builtin.CachedModule.cache[
                                                            self.source_path]
            except KeyError:
                return None, 0
            part_parser = self.module.get_part_parser()
            user_stmt = part_parser.user_stmt
            call, index = check_user_stmt(user_stmt)
            if call:
                old_stmt = parser.module.get_statement_for_position(self.pos)
                if old_stmt is None:
                    return None, 0
                old_call, old_index = check_user_stmt(old_stmt)
                if old_call:
                    # compare repr because that should definitely be the same.
                    # Otherwise the whole thing is out of sync.
                    if repr(old_call) == repr(call):
                        # return the index of the part_parser
                        return old_call, index
                return None, 0
            else:
                raise NotFoundError()

        debug.speed('func_call start')
        try:
            call, index = check_cache()
        except NotFoundError:
            return None
        debug.speed('func_call parsed')

        if call is None:
            # This is a backup, if the above is not successful.
            user_stmt = self.parser.user_stmt
            call, index = check_user_stmt(user_stmt)
            if call is None:
                return None

        debug.speed('func_call user_stmt')
        with helpers.scale_speed_settings(settings.scale_get_in_function_call):
            origins = evaluate.follow_call(call)
        debug.speed('func_call followed')

        if len(origins) == 0:
            return None
        # just take entry zero, because we need just one.
        executable = origins[0]

        return api_classes.CallDef(executable, index, call)

    def _get_on_import_stmt(self, is_like_search=False):
        """ Resolve the user statement, if it is an import. Only resolve the
        parts until the user position. """
        user_stmt = self.parser.user_stmt
        import_names = user_stmt.get_all_import_names()
        kill_count = -1
        cur_name_part = None
        for i in import_names:
            if user_stmt.alias == i:
                continue
            for name_part in i.names:
                if name_part.end_pos >= self.pos:
                    if not cur_name_part:
                        cur_name_part = name_part
                    kill_count += 1

        i = imports.ImportPath(user_stmt, is_like_search,
                                kill_count=kill_count, direct_resolve=True)
        return i, cur_name_part

    def _get_completion_parts(self, path):
        """
        Returns the parts for the completion
        :return: tuple - (path, dot, like)
        """
        match = re.match(r'^(.*?)(\.|)(\w?[\w\d]*)$', path, flags=re.S)
        return match.groups()

    def __del__(self):
        evaluate.clear_caches()


def set_debug_function(func_cb=debug.print_to_stdout, warnings=True,
                                            notices=True, speed=True):
    """
    You can define a callback debug function to get all the debug messages.
    :param func_cb: The callback function for debug messages, with n params.
    """
    debug.debug_function = func_cb
    debug.enable_warning = warnings
    debug.enable_notice = notices
    debug.enable_speed = speed
