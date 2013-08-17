"""
The API basically only provides one class. You can create a :class:`Script` and
use its methods.

Additionally you can add a debug function with :func:`set_debug_function` and
catch :exc:`NotFoundError` which is being raised if your completion is not
possible.
"""
from __future__ import with_statement

import re
import os
import warnings
from itertools import chain

from jedi import parsing
from jedi import parsing_representation as pr
from jedi import debug
from jedi import settings
from jedi import helpers
from jedi import common
from jedi import cache
from jedi import modules
from jedi import interpret
from jedi._compatibility import next, unicode, builtins
import keywords
import evaluate
import api_classes
import evaluate_representation as er
import dynamic
import imports
import builtin


class NotFoundError(Exception):
    """A custom error to avoid catching the wrong exceptions."""


class Script(object):
    """
    A Script is the base for completions, goto or whatever you want to do with
    |jedi|.

    :param source: The source code of the current file, separated by newlines.
    :type source: str
    :param line: The line to perform actions on (starting with 1).
    :type line: int
    :param col: The column of the cursor (starting with 0).
    :type col: int
    :param path: The path of the file in the file system, or ``''`` if
        it hasn't been saved yet.
    :type path: str or None
    :param source_encoding: The encoding of ``source``, if it is not a
        ``unicode`` object (default ``'utf-8'``).
    :type source_encoding: str
    """
    def __init__(self, source, line=None, column=None, path=None,
                 source_encoding='utf-8', source_path=None):
        if source_path is not None:
            warnings.warn("Use path instead of source_path.", DeprecationWarning)
            path = source_path

        lines = source.splitlines()
        if source and source[-1] == '\n':
            lines.append('')

        self._line = max(len(lines), 1) if line is None else line
        self._column = len(lines[-1]) if column is None else column

        api_classes._clear_caches()
        debug.reset_time()
        self.source = modules.source_to_unicode(source, source_encoding)
        self.pos = self._line, self._column
        self._module = modules.ModuleWithCursor(
            path, source=self.source, position=self.pos)
        self._source_path = path
        self.path = None if path is None else os.path.abspath(path)
        debug.speed('init')

    @property
    def source_path(self):
        """
        .. deprecated:: 0.7.0
           Use :attr:`.path` instead.
        .. todo:: Remove!
        """
        warnings.warn("Use path instead of source_path.", DeprecationWarning)
        return self.path

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, repr(self._source_path))

    @property
    def _parser(self):
        """ lazy parser."""
        return self._module.parser

    @api_classes._clear_caches_after_call
    def completions(self):
        """
        Return :class:`api_classes.Completion` objects. Those objects contain
        information about the completions, more than just names.

        :return: Completion objects, sorted by name and __ comes last.
        :rtype: list of :class:`api_classes.Completion`
        """
        def get_completions(user_stmt, bs):
            if isinstance(user_stmt, pr.Import):
                context = self._module.get_context()
                next(context)  # skip the path
                if next(context) == 'from':
                    # completion is just "import" if before stands from ..
                    return ((k, bs) for k in keywords.keyword_names('import'))
            return self._simple_complete(path, like)

        debug.speed('completions start')
        path = self._module.get_path_until_cursor()
        if re.search('^\.|\.\.$', path):
            return []
        path, dot, like = self._get_completion_parts()

        user_stmt = self._user_stmt(True)
        bs = builtin.Builtin.scope
        completions = get_completions(user_stmt, bs)

        if not dot:  # named params have no dots
            for call_def in self.call_signatures():
                if not call_def.module.is_builtin():
                    for p in call_def.params:
                        completions.append((p.get_name(), p))

            if not path and not isinstance(user_stmt, pr.Import):
                # add keywords
                completions += ((k, bs) for k in keywords.keyword_names(
                    all=True))

        needs_dot = not dot and path

        comps = []
        comp_dct = {}
        for c, s in set(completions):
            n = c.names[-1]
            if settings.case_insensitive_completion \
                    and n.lower().startswith(like.lower()) \
                    or n.startswith(like):
                if not evaluate.filter_private_variable(s,
                        user_stmt or self._parser.user_scope, n):
                    new = api_classes.Completion(c, needs_dot, len(like), s)
                    k = (new.name, new.complete)  # key
                    if k in comp_dct and settings.no_completion_duplicates:
                        comp_dct[k]._same_name_completions.append(new)
                    else:
                        comp_dct[k] = new
                        comps.append(new)

        debug.speed('completions end')

        return sorted(comps, key=lambda x: (x.name.startswith('__'),
                                            x.name.startswith('_'),
                                            x.name.lower()))

    def _simple_complete(self, path, like):
        try:
            scopes = list(self._prepare_goto(path, True))
        except NotFoundError:
            scopes = []
            scope_generator = evaluate.get_names_of_scope(
                self._parser.user_scope, self.pos)
            completions = []
            for scope, name_list in scope_generator:
                for c in name_list:
                    completions.append((c, scope))
        else:
            completions = []
            debug.dbg('possible scopes', scopes)
            for s in scopes:
                if s.isinstance(er.Function):
                    names = s.get_magic_method_names()
                else:
                    if isinstance(s, imports.ImportPath):
                        under = like + self._module.get_path_after_cursor()
                        if under == 'import':
                            current_line = self._module.get_position_line()
                            if not current_line.endswith('import import'):
                                continue
                        a = s.import_stmt.alias
                        if a and a.start_pos <= self.pos <= a.end_pos:
                            continue
                        names = s.get_defined_names(on_import_stmt=True)
                    else:
                        names = s.get_defined_names()

                for c in names:
                    completions.append((c, s))
        return completions

    def _user_stmt(self, is_completion=False):
        user_stmt = self._parser.user_stmt
        debug.speed('parsed')

        if is_completion and not user_stmt:
            # for statements like `from x import ` (cursor not in statement)
            pos = next(self._module.get_context(yield_positions=True))
            last_stmt = pos and self._parser.module.get_statement_for_position(
                                pos, include_imports=True)
            if isinstance(last_stmt, pr.Import):
                user_stmt = last_stmt
        return user_stmt

    def _prepare_goto(self, goto_path, is_completion=False):
        """
        Base for completions/goto. Basically it returns the resolved scopes
        under cursor.
        """
        debug.dbg('start: %s in %s' % (goto_path, self._parser.user_scope))

        user_stmt = self._user_stmt(is_completion)
        if not user_stmt and len(goto_path.split('\n')) > 1:
            # If the user_stmt is not defined and the goto_path is multi line,
            # something's strange. Most probably the backwards tokenizer
            # matched to much.
            return []

        if isinstance(user_stmt, pr.Import):
            scopes = [self._get_on_import_stmt(user_stmt, is_completion)[0]]
        else:
            # just parse one statement, take it and evaluate it
            stmt = self._get_under_cursor_stmt(goto_path)
            scopes = evaluate.follow_statement(stmt)
        return scopes

    def _get_under_cursor_stmt(self, cursor_txt):
        offset = self.pos[0] - 1, self.pos[1]
        r = parsing.Parser(cursor_txt, no_docstr=True, offset=offset)
        try:
            stmt = r.module.statements[0]
        except IndexError:
            raise NotFoundError()
        stmt.parent = self._parser.user_scope
        return stmt

    def complete(self):
        """
        .. deprecated:: 0.6.0
           Use :attr:`.completions` instead.
        .. todo:: Remove!
        """
        warnings.warn("Use completions instead.", DeprecationWarning)
        return self.completions()

    def goto(self):
        """
        .. deprecated:: 0.6.0
           Use :attr:`.goto_assignments` instead.
        .. todo:: Remove!
        """
        warnings.warn("Use goto_assignments instead.", DeprecationWarning)
        return self.goto_assignments()

    def definition(self):
        """
        .. deprecated:: 0.6.0
           Use :attr:`.goto_definitions` instead.
        .. todo:: Remove!
        """
        warnings.warn("Use goto_definitions instead.", DeprecationWarning)
        return self.goto_definitions()

    def get_definition(self):
        """
        .. deprecated:: 0.5.0
           Use :attr:`.goto_definitions` instead.
        .. todo:: Remove!
        """
        warnings.warn("Use goto_definitions instead.", DeprecationWarning)
        return self.goto_definitions()

    def related_names(self):
        """
        .. deprecated:: 0.6.0
           Use :attr:`.usages` instead.
        .. todo:: Remove!
        """
        warnings.warn("Use usages instead.", DeprecationWarning)
        return self.usages()

    def get_in_function_call(self):
        """
        .. deprecated:: 0.6.0
           Use :attr:`.call_signatures` instead.
        .. todo:: Remove!
        """
        return self.function_definition()

    def function_definition(self):
        """
        .. deprecated:: 0.6.0
           Use :attr:`.call_signatures` instead.
        .. todo:: Remove!
        """
        warnings.warn("Use line instead.", DeprecationWarning)
        sig = self.call_signatures()
        return sig[0] if sig else None

    @api_classes._clear_caches_after_call
    def goto_definitions(self):
        """
        Return the definitions of a the path under the cursor.  goto function!
        This follows complicated paths and returns the end, not the first
        definition. The big difference between :meth:`goto_assignments` and
        :meth:`goto_definitions` is that :meth:`goto_assignments` doesn't
        follow imports and statements. Multiple objects may be returned,
        because Python itself is a dynamic language, which means depending on
        an option you can have two different versions of a function.

        :rtype: list of :class:`api_classes.Definition`
        """
        def resolve_import_paths(scopes):
            for s in scopes.copy():
                if isinstance(s, imports.ImportPath):
                    scopes.remove(s)
                    scopes.update(resolve_import_paths(set(s.follow())))
            return scopes

        goto_path = self._module.get_path_under_cursor()

        context = self._module.get_context()
        scopes = set()
        lower_priority_operators = ('()', '(', ',')
        """Operators that could hide callee."""
        if next(context) in ('class', 'def'):
            scopes = set([self._module.parser.user_scope])
        elif not goto_path:
            op = self._module.get_operator_under_cursor()
            if op and op not in lower_priority_operators:
                scopes = set([keywords.get_operator(op, self.pos)])

        # Fetch definition of callee
        if not goto_path:
            (call, _) = self._func_call_and_param_index()
            if call is not None:
                while call.next is not None:
                    call = call.next
                # reset cursor position:
                (row, col) = call.name.end_pos
                self.pos = (row, max(col - 1, 0))
                self._module = modules.ModuleWithCursor(
                    self._source_path,
                    source=self.source,
                    position=self.pos)
                # then try to find the path again
                goto_path = self._module.get_path_under_cursor()

        if not scopes:
            if goto_path:
                scopes = set(self._prepare_goto(goto_path))
            elif op in lower_priority_operators:
                scopes = set([keywords.get_operator(op, self.pos)])

        scopes = resolve_import_paths(scopes)

        # add keywords
        scopes |= keywords.keywords(string=goto_path, pos=self.pos)

        d = set([api_classes.Definition(s) for s in scopes
                 if not isinstance(s, imports.ImportPath._GlobalNamespace)])
        return self._sorted_defs(d)

    @api_classes._clear_caches_after_call
    def goto_assignments(self):
        """
        Return the first definition found. Imports and statements aren't
        followed. Multiple objects may be returned, because Python itself is a
        dynamic language, which means depending on an option you can have two
        different versions of a function.

        :rtype: list of :class:`api_classes.Definition`
        """
        results, _ = self._goto()
        d = [api_classes.Definition(d) for d in set(results)
             if not isinstance(d, imports.ImportPath._GlobalNamespace)]
        return self._sorted_defs(d)

    def _goto(self, add_import_name=False):
        """
        Used for goto_assignments and usages.

        :param add_import_name: Add the the name (if import) to the result.
        """
        def follow_inexistent_imports(defs):
            """ Imports can be generated, e.g. following
            `multiprocessing.dummy` generates an import dummy in the
            multiprocessing module. The Import doesn't exist -> follow.
            """
            definitions = set(defs)
            for d in defs:
                if isinstance(d.parent, pr.Import) \
                        and d.start_pos == (0, 0):
                    i = imports.ImportPath(d.parent).follow(is_goto=True)
                    definitions.remove(d)
                    definitions |= follow_inexistent_imports(i)
            return definitions

        goto_path = self._module.get_path_under_cursor()
        context = self._module.get_context()
        user_stmt = self._user_stmt()
        if next(context) in ('class', 'def'):
            user_scope = self._parser.user_scope
            definitions = set([user_scope.name])
            search_name = unicode(user_scope.name)
        elif isinstance(user_stmt, pr.Import):
            s, name_part = self._get_on_import_stmt(user_stmt)
            try:
                definitions = [s.follow(is_goto=True)[0]]
            except IndexError:
                definitions = []
            search_name = unicode(name_part)

            if add_import_name:
                import_name = user_stmt.get_defined_names()
                # imports have only one name
                if not user_stmt.star \
                        and name_part == import_name[0].names[-1]:
                    definitions.append(import_name[0])
        else:
            stmt = self._get_under_cursor_stmt(goto_path)
            defs, search_name = evaluate.goto(stmt)
            definitions = follow_inexistent_imports(defs)
            if isinstance(user_stmt, pr.Statement):
                c = user_stmt.get_commands()
                if c and not isinstance(c[0], (str, unicode)) and \
                   c[0].start_pos > self.pos:
                    # The cursor must be after the start, otherwise the
                    # statement is just an assignee.
                    definitions = [user_stmt]
        return definitions, search_name

    @api_classes._clear_caches_after_call
    def usages(self, additional_module_paths=()):
        """
        Return :class:`api_classes.Usage` objects, which contain all
        names that point to the definition of the name under the cursor. This
        is very useful for refactoring (renaming), or to show all usages of a
        variable.

        .. todo:: Implement additional_module_paths

        :rtype: list of :class:`api_classes.Usage`
        """
        temp, settings.dynamic_flow_information = \
            settings.dynamic_flow_information, False
        user_stmt = self._user_stmt()
        definitions, search_name = self._goto(add_import_name=True)
        if isinstance(user_stmt, pr.Statement):
            c = user_stmt.get_commands()[0]
            if not isinstance(c, unicode) and self.pos < c.start_pos:
                # the search_name might be before `=`
                definitions = [v for v in user_stmt.set_vars
                               if unicode(v.names[-1]) == search_name]
        if not isinstance(user_stmt, pr.Import):
            # import case is looked at with add_import_name option
            definitions = dynamic.usages_add_import_modules(definitions,
                                                            search_name)

        module = set([d.get_parent_until() for d in definitions])
        module.add(self._parser.module)
        names = dynamic.usages(definitions, search_name, module)

        for d in set(definitions):
            if isinstance(d, pr.Module):
                names.append(api_classes.Usage(d, d))
            elif isinstance(d, er.Instance):
                # Instances can be ignored, because they are being created by
                # ``__getattr__``.
                pass
            else:
                names.append(api_classes.Usage(d.names[-1], d))

        settings.dynamic_flow_information = temp
        return self._sorted_defs(set(names))

    @api_classes._clear_caches_after_call
    def call_signatures(self):
        """
        Return the function object of the call you're currently in.

        E.g. if the cursor is here::

            abs(# <-- cursor is here

        This would return the ``abs`` function. On the other hand::

            abs()# <-- cursor is here

        This would return ``None``.

        :rtype: :class:`api_classes.CallDef`
        """

        call, index = self._func_call_and_param_index()
        if call is None:
            return []

        user_stmt = self._user_stmt()
        with common.scale_speed_settings(settings.scale_function_definition):
            _callable = lambda: evaluate.follow_call(call)
            origins = cache.cache_function_definition(_callable, user_stmt)
        debug.speed('func_call followed')

        return [api_classes.CallDef(o, index, call) for o in origins
                if o.isinstance(er.Function, er.Instance, er.Class)]

    def _func_call_and_param_index(self):
        debug.speed('func_call start')
        call, index = None, 0
        if call is None:
            user_stmt = self._user_stmt()
            if user_stmt is not None and isinstance(user_stmt, pr.Statement):
                call, index, _ = helpers.search_function_definition(
                    user_stmt, self.pos)
        debug.speed('func_call parsed')
        return call, index

    def _get_on_import_stmt(self, user_stmt, is_like_search=False):
        """ Resolve the user statement, if it is an import. Only resolve the
        parts until the user position. """
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


        context = self._module.get_context()
        just_from = next(context) == 'from'

        i = imports.ImportPath(user_stmt, is_like_search,
                               kill_count=kill_count, direct_resolve=True,
                               is_just_from=just_from)
        return i, cur_name_part

    def _get_completion_parts(self):
        """
        Returns the parts for the completion
        :return: tuple - (path, dot, like)
        """
        path = self._module.get_path_until_cursor()
        match = re.match(r'^(.*?)(\.|)(\w?[\w\d]*)$', path, flags=re.S)
        return match.groups()

    @staticmethod
    def _sorted_defs(d):
        # Note: `or ''` below is required because `module_path` could be
        #       None and you can't compare None and str in Python 3.
        return sorted(d, key=lambda x: (x.module_path or '', x.line, x.column))


class Interpreter(Script):

    """
    Jedi API for Python REPLs.

    In addition to completion of simple attribute access, Jedi
    supports code completion based on static code analysis.
    Jedi can complete attributes of object which is not initialized
    yet.

    >>> from os.path import join
    >>> namespace = locals()
    >>> script = Interpreter('join().up', [namespace])
    >>> print(script.completions()[0].name)
    upper

    """

    def __init__(self, source, namespaces=[], **kwds):
        """
        Parse `source` and mixin interpreted Python objects from `namespaces`.

        :type source: str
        :arg  source: Code to parse.
        :type namespaces: list of dict
        :arg  namespaces: a list of namespace dictionaries such as the one
                          returned by :func:`locals`.

        Other optional arguments are same as the ones for :class:`Script`.
        If `line` and `column` are None, they are assumed be at the end of
        `source`.
        """
        super(Interpreter, self).__init__(source, **kwds)
        self.namespaces = namespaces

        # Here we add the namespaces to the current parser.
        importer = interpret.ObjectImporter(self._parser.user_scope)
        for ns in namespaces:
            importer.import_raw_namespace(ns)

    def _simple_complete(self, path, like):
        user_stmt = self._user_stmt(True)
        is_simple_path = not path or re.search('^[\w][\w\d.]*$', path)
        if isinstance(user_stmt, pr.Import) or not is_simple_path:
            return super(type(self), self)._simple_complete(path, like)
        else:
            class NamespaceModule:
                def __getattr__(_, name):
                    for n in self.namespaces:
                        try:
                            return n[name]
                        except KeyError:
                            pass
                    raise AttributeError()

                def __dir__(_):
                    return list(set(chain.from_iterable(n.keys()
                                    for n in self.namespaces)))

            paths = path.split('.') if path else []

            namespaces = (NamespaceModule(), builtins)
            for p in paths:
                old, namespaces = namespaces, []
                for n in old:
                    try:
                        namespaces.append(getattr(n, p))
                    except AttributeError:
                        pass

            completions = []
            for n in namespaces:
                for name in dir(n):
                    if name.lower().startswith(like.lower()):
                        scope = self._parser.module
                        n = pr.Name(self._parser.module, [(name, (0, 0))],
                                    (0, 0), (0, 0), scope)
                        completions.append((n, scope))
            return completions




def defined_names(source, path=None, source_encoding='utf-8'):
    """
    Get all definitions in `source` sorted by its position.

    This functions can be used for listing functions, classes and
    data defined in a file.  This can be useful if you want to list
    them in "sidebar".  Each element in the returned list also has
    `defined_names` method which can be used to get sub-definitions
    (e.g., methods in class).

    :rtype: list of api_classes.Definition
    """
    parser = parsing.Parser(
        modules.source_to_unicode(source, source_encoding),
        module_path=path,
    )
    return api_classes._defined_names(parser.module)


def preload_module(*modules):
    """
    Preloading modules tells Jedi to load a module now, instead of lazy parsing
    of modules. Usful for IDEs, to control which modules to load on startup.

    :param modules: different module names, list of string.
    """
    for m in modules:
        s = "import %s as x; x." % m
        Script(s, 1, len(s), None).completions()


def set_debug_function(func_cb=debug.print_to_stdout, warnings=True,
                       notices=True, speed=True):
    """
    Define a callback debug function to get all the debug messages.

    :param func_cb: The callback function for debug messages, with n params.
    """
    debug.debug_function = func_cb
    debug.enable_warning = warnings
    debug.enable_notice = notices
    debug.enable_speed = speed
