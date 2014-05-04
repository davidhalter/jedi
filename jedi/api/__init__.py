"""
The API basically only provides one class. You can create a :class:`Script` and
use its methods.

Additionally you can add a debug function with :func:`set_debug_function` and
catch :exc:`NotFoundError` which is being raised if your completion is not
possible.

.. warning:: Please, note that Jedi is **not thread safe**.
"""
import re
import os
import warnings
import sys
from itertools import chain

from jedi._compatibility import next, unicode, builtins
from jedi.parser import Parser
from jedi.parser.tokenize import source_tokens
from jedi.parser import representation as pr
from jedi.parser.user_context import UserContext, UserContextParser
from jedi import debug
from jedi import settings
from jedi import common
from jedi import cache
from jedi.api import keywords
from jedi.api import classes
from jedi.api import interpreter
from jedi.api import usages
from jedi.api import helpers
from jedi.evaluate import Evaluator, filter_private_variable
from jedi.evaluate import representation as er
from jedi.evaluate import compiled
from jedi.evaluate import imports
from jedi.evaluate.helpers import FakeName
from jedi.evaluate.finder import get_names_of_scope
from jedi.evaluate.helpers import search_call_signatures

# Jedi uses lots and lots of recursion. By setting this a little bit higher, we
# can remove some "maximum recursion depth" errors.
sys.setrecursionlimit(2000)


class NotFoundError(Exception):
    """A custom error to avoid catching the wrong exceptions."""


class Script(object):
    """
    A Script is the base for completions, goto or whatever you want to do with
    |jedi|.

    You can either use the ``source`` parameter or ``path`` to read a file.
    Usually you're going to want to use both of them (in an editor).

    :param source: The source code of the current file, separated by newlines.
    :type source: str
    :param line: The line to perform actions on (starting with 1).
    :type line: int
    :param col: The column of the cursor (starting with 0).
    :type col: int
    :param path: The path of the file in the file system, or ``''`` if
        it hasn't been saved yet.
    :type path: str or None
    :param encoding: The encoding of ``source``, if it is not a
        ``unicode`` object (default ``'utf-8'``).
    :type encoding: str
    :param source_encoding: The encoding of ``source``, if it is not a
        ``unicode`` object (default ``'utf-8'``).
    :type encoding: str
    """
    def __init__(self, source=None, line=None, column=None, path=None,
                 encoding='utf-8', source_path=None, source_encoding=None):
        if source_path is not None:
            warnings.warn("Use path instead of source_path.", DeprecationWarning)
            path = source_path
        if source_encoding is not None:
            warnings.warn("Use encoding instead of source_encoding.", DeprecationWarning)
            encoding = source_encoding

        self._orig_path = path
        self.path = None if path is None else os.path.abspath(path)

        if source is None:
            with open(path) as f:
                source = f.read()

        lines = source.splitlines() or ['']
        if source and source[-1] == '\n':
            lines.append('')
        line = max(len(lines), 1) if line is None else line
        if not (0 < line <= len(lines)):
            raise ValueError('`line` parameter is not in a valid range.')

        line_len = len(lines[line - 1])
        column = line_len if column is None else column
        if not (0 <= column <= line_len):
            raise ValueError('`column` parameter is not in a valid range.')
        self._pos = line, column

        cache.clear_caches()
        debug.reset_time()
        self.source = common.source_to_unicode(source, encoding)
        self._user_context = UserContext(self.source, self._pos)
        self._parser = UserContextParser(self.source, path, self._pos, self._user_context)
        self._evaluator = Evaluator()
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
        return '<%s: %s>' % (self.__class__.__name__, repr(self._orig_path))

    def completions(self):
        """
        Return :class:`classes.Completion` objects. Those objects contain
        information about the completions, more than just names.

        :return: Completion objects, sorted by name and __ comes last.
        :rtype: list of :class:`classes.Completion`
        """
        def get_completions(user_stmt, bs):
            if isinstance(user_stmt, pr.Import):
                context = self._user_context.get_context()
                next(context)  # skip the path
                if next(context) == 'from':
                    # completion is just "import" if before stands from ..
                    return ((k, bs) for k in keywords.keyword_names('import'))
            return self._simple_complete(path, like)

        def completion_possible(path):
            """
            The completion logic is kind of complicated, because we strip the
            last word part. To ignore certain strange patterns with dots, just
            use regex.
            """
            if re.match('\d+\.\.$|\.{4}$', path):
                return True  # check Ellipsis and float literal `1.`

            return not re.search(r'^\.|^\d\.$|\.\.$', path)

        debug.speed('completions start')
        path = self._user_context.get_path_until_cursor()
        if not completion_possible(path):
            return []
        path, dot, like = helpers.completion_parts(path)

        user_stmt = self._parser.user_stmt_with_whitespace()
        b = compiled.builtin
        completions = get_completions(user_stmt, b)

        if not dot:
            # add named params
            for call_sig in self.call_signatures():
                # allow protected access, because it's a public API.
                module = call_sig._definition.get_parent_until()
                # Compiled modules typically don't allow keyword arguments.
                if not isinstance(module, compiled.CompiledObject):
                    for p in call_sig.params:
                        # Allow access on _definition here, because it's a
                        # public API and we don't want to make the internal
                        # Name object public.
                        if p._definition.stars == 0:  # no *args/**kwargs
                            completions.append((p._definition.get_name(), p))

            if not path and not isinstance(user_stmt, pr.Import):
                # add keywords
                completions += ((k, b) for k in keywords.keyword_names(all=True))

        needs_dot = not dot and path

        comps = []
        comp_dct = {}
        for c, s in set(completions):
            n = str(c.names[-1])
            if settings.case_insensitive_completion \
                    and n.lower().startswith(like.lower()) \
                    or n.startswith(like):
                if not filter_private_variable(s, user_stmt or self._parser.user_scope(), n):
                    new = classes.Completion(self._evaluator, c, needs_dot, len(like), s)
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
            scope_generator = get_names_of_scope(self._evaluator,
                                                 self._parser.user_scope(),
                                                 self._pos)
            completions = []
            for scope, name_list in scope_generator:
                for c in name_list:
                    completions.append((c, scope))
        else:
            completions = []
            debug.dbg('possible completion scopes: %s', scopes)
            for s in scopes:
                if s.isinstance(er.Function):
                    names = s.get_magic_function_names()
                else:
                    if isinstance(s, imports.ImportWrapper):
                        under = like + self._user_context.get_path_after_cursor()
                        if under == 'import':
                            current_line = self._user_context.get_position_line()
                            if not current_line.endswith('import import'):
                                continue
                        a = s.import_stmt.alias
                        if a and a.start_pos <= self._pos <= a.end_pos:
                            continue
                        names = s.get_defined_names(on_import_stmt=True)
                    else:
                        names = s.get_defined_names()

                for c in names:
                    completions.append((c, s))
        return completions

    def _prepare_goto(self, goto_path, is_completion=False):
        """
        Base for completions/goto. Basically it returns the resolved scopes
        under cursor.
        """
        debug.dbg('start: %s in %s', goto_path, self._parser.user_scope())

        user_stmt = self._parser.user_stmt_with_whitespace()
        if not user_stmt and len(goto_path.split('\n')) > 1:
            # If the user_stmt is not defined and the goto_path is multi line,
            # something's strange. Most probably the backwards tokenizer
            # matched to much.
            return []

        if isinstance(user_stmt, pr.Import):
            scopes = [helpers.get_on_import_stmt(self._evaluator, self._user_context,
                                                 user_stmt, is_completion)[0]]
        else:
            # just parse one statement, take it and evaluate it
            eval_stmt = self._get_under_cursor_stmt(goto_path)

            if not is_completion:
                # goto_definition returns definitions of its statements if the
                # cursor is on the assignee. By changing the start_pos of our
                # "pseud" statement, the Jedi evaluator can find the assignees.
                if user_stmt is not None:
                    eval_stmt.start_pos = user_stmt.end_pos
            scopes = self._evaluator.eval_statement(eval_stmt)
        return scopes

    def _get_under_cursor_stmt(self, cursor_txt):
        tokenizer = source_tokens(cursor_txt, line_offset=self._pos[0] - 1)
        r = Parser(cursor_txt, no_docstr=True, tokenizer=tokenizer)
        try:
            # Take the last statement available.
            stmt = r.module.statements[-1]
        except IndexError:
            raise NotFoundError()
        if not isinstance(stmt, pr.Statement):
            raise NotFoundError()

        user_stmt = self._parser.user_stmt()
        if user_stmt is None:
            # Set the start_pos to a pseudo position, that doesn't exist but works
            # perfectly well (for both completions in docstrings and statements).
            stmt.start_pos = self._pos
        else:
            stmt.start_pos = user_stmt.start_pos
        stmt.parent = self._parser.user_scope()
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

    def goto_definitions(self):
        """
        Return the definitions of a the path under the cursor.  goto function!
        This follows complicated paths and returns the end, not the first
        definition. The big difference between :meth:`goto_assignments` and
        :meth:`goto_definitions` is that :meth:`goto_assignments` doesn't
        follow imports and statements. Multiple objects may be returned,
        because Python itself is a dynamic language, which means depending on
        an option you can have two different versions of a function.

        :rtype: list of :class:`classes.Definition`
        """
        def resolve_import_paths(scopes):
            for s in scopes.copy():
                if isinstance(s, imports.ImportWrapper):
                    scopes.remove(s)
                    scopes.update(resolve_import_paths(set(s.follow())))
            return scopes

        user_stmt = self._parser.user_stmt_with_whitespace()
        goto_path = self._user_context.get_path_under_cursor()
        context = self._user_context.get_context()
        definitions = set()
        if next(context) in ('class', 'def'):
            definitions = set([self._parser.user_scope()])
        else:
            # Fetch definition of callee, if there's no path otherwise.
            if not goto_path:
                (call, _) = search_call_signatures(user_stmt, self._pos)
                if call is not None:
                    while call.next is not None:
                        call = call.next
                    # reset cursor position:
                    (row, col) = call.name.end_pos
                    pos = (row, max(col - 1, 0))
                    self._user_context = UserContext(self.source, pos)
                    # then try to find the path again
                    goto_path = self._user_context.get_path_under_cursor()

        if not definitions:
            if goto_path:
                definitions = set(self._prepare_goto(goto_path))

        definitions = resolve_import_paths(definitions)
        d = set([classes.Definition(self._evaluator, s) for s in definitions
                 if s is not imports.ImportWrapper.GlobalNamespace])
        return helpers.sorted_definitions(d)

    def goto_assignments(self):
        """
        Return the first definition found. Imports and statements aren't
        followed. Multiple objects may be returned, because Python itself is a
        dynamic language, which means depending on an option you can have two
        different versions of a function.

        :rtype: list of :class:`classes.Definition`
        """
        results, _ = self._goto()
        d = [classes.Definition(self._evaluator, d) for d in set(results)
             if d is not imports.ImportWrapper.GlobalNamespace]
        return helpers.sorted_definitions(d)

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
                    i = imports.ImportWrapper(self._evaluator, d.parent).follow(is_goto=True)
                    definitions.remove(d)
                    definitions |= follow_inexistent_imports(i)
            return definitions

        goto_path = self._user_context.get_path_under_cursor()
        context = self._user_context.get_context()
        user_stmt = self._parser.user_stmt()
        if next(context) in ('class', 'def'):
            user_scope = self._parser.user_scope()
            definitions = set([user_scope.name])
            search_name = unicode(user_scope.name)
        elif isinstance(user_stmt, pr.Import):
            s, name_part = helpers.get_on_import_stmt(self._evaluator,
                                                      self._user_context, user_stmt)
            try:
                definitions = [s.follow(is_goto=True)[0]]
            except IndexError:
                definitions = []
            search_name = unicode(name_part)

            if add_import_name:
                import_name = user_stmt.get_defined_names()
                # imports have only one name
                if not user_stmt.star \
                        and unicode(name_part) == unicode(import_name[0].names[-1]):
                    definitions.append(import_name[0])
        else:
            stmt = self._get_under_cursor_stmt(goto_path)

            def test_lhs():
                """
                Special rule for goto, left hand side of the statement returns
                itself, if the name is ``foo``, but not ``foo.bar``.
                """
                if isinstance(user_stmt, pr.Statement):
                    for name in user_stmt.get_defined_names():
                        if name.start_pos <= self._pos <= name.end_pos \
                                and len(name.names) == 1:
                            return name, unicode(name.names[-1])
                return None, None

            lhs, search_name = test_lhs()
            if lhs is None:
                expression_list = stmt.expression_list()
                if len(expression_list) == 0:
                    return [], ''
                # Only the first command is important, the rest should basically not
                # happen except in broken code (e.g. docstrings that aren't code).
                call = expression_list[0]
                if isinstance(call, pr.Call):
                    call_path = list(call.generate_call_path())
                else:
                    call_path = [call]

                defs, search_name_part = self._evaluator.goto(stmt, call_path)
                search_name = unicode(search_name_part)
                definitions = follow_inexistent_imports(defs)
            else:
                definitions = [lhs]
            if isinstance(user_stmt, pr.Statement):
                c = user_stmt.expression_list()
                if c and not isinstance(c[0], (str, unicode)) \
                        and c[0].start_pos > self._pos \
                        and not re.search(r'\.\w+$', goto_path):
                    # The cursor must be after the start, otherwise the
                    # statement is just an assignee.
                    definitions = [user_stmt]
        return definitions, search_name

    def usages(self, additional_module_paths=()):
        """
        Return :class:`classes.Definition` objects, which contain all
        names that point to the definition of the name under the cursor. This
        is very useful for refactoring (renaming), or to show all usages of a
        variable.

        .. todo:: Implement additional_module_paths

        :rtype: list of :class:`classes.Definition`
        """
        temp, settings.dynamic_flow_information = \
            settings.dynamic_flow_information, False
        user_stmt = self._parser.user_stmt()
        definitions, search_name = self._goto(add_import_name=True)
        if isinstance(user_stmt, pr.Statement):
            c = user_stmt.expression_list()[0]
            if not isinstance(c, unicode) and self._pos < c.start_pos:
                # the search_name might be before `=`
                definitions = [v for v in user_stmt.get_defined_names()
                               if unicode(v.names[-1]) == search_name]
        if not isinstance(user_stmt, pr.Import):
            # import case is looked at with add_import_name option
            definitions = usages.usages_add_import_modules(self._evaluator, definitions, search_name)

        module = set([d.get_parent_until() for d in definitions])
        module.add(self._parser.module())
        names = usages.usages(self._evaluator, definitions, search_name, module)

        for d in set(definitions):
            try:
                name_part = d.names[-1]
            except AttributeError:
                names.append(classes.Definition(self._evaluator, d))
            else:
                names.append(classes.Definition(self._evaluator, name_part))

        settings.dynamic_flow_information = temp
        return helpers.sorted_definitions(set(names))

    def call_signatures(self):
        """
        Return the function object of the call you're currently in.

        E.g. if the cursor is here::

            abs(# <-- cursor is here

        This would return the ``abs`` function. On the other hand::

            abs()# <-- cursor is here

        This would return ``None``.

        :rtype: list of :class:`classes.CallSignature`
        """
        user_stmt = self._parser.user_stmt_with_whitespace()
        call, index = search_call_signatures(user_stmt, self._pos)
        if call is None:
            return []

        stmt_el = call
        while isinstance(stmt_el.parent, pr.StatementElement):
            # Go to parent literal/variable until not possible anymore. This
            # makes it possible to return the whole expression.
            stmt_el = stmt_el.parent
        # We can reset the execution since it's a new object
        # (fast_parent_copy).
        execution_arr, call.execution = call.execution, None

        with common.scale_speed_settings(settings.scale_call_signatures):
            _callable = lambda: self._evaluator.eval_call(stmt_el)
            origins = cache.cache_call_signatures(_callable, self.source,
                                                  self._pos, user_stmt)
            origins = self._evaluator.eval_call(stmt_el)
        debug.speed('func_call followed')

        key_name = None
        try:
            detail = execution_arr[index].assignment_details[0]
        except IndexError:
            pass
        else:
            try:
                key_name = unicode(detail[0][0].name)
            except (IndexError, AttributeError):
                pass
        return [classes.CallSignature(self._evaluator, o, call, index, key_name)
                for o in origins if o.is_callable()]


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
        interpreter.create(self._evaluator, namespaces[0], self._parser.module())

    def _simple_complete(self, path, like):
        user_stmt = self._parser.user_stmt_with_whitespace()
        is_simple_path = not path or re.search('^[\w][\w\d.]*$', path)
        if isinstance(user_stmt, pr.Import) or not is_simple_path:
            return super(type(self), self)._simple_complete(path, like)
        else:
            class NamespaceModule(object):
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
            for namespace in namespaces:
                for name in dir(namespace):
                    if name.lower().startswith(like.lower()):
                        scope = self._parser.module()
                        n = FakeName(name, scope)
                        completions.append((n, scope))
            return completions


def defined_names(source, path=None, encoding='utf-8'):
    """
    Get all definitions in `source` sorted by its position.

    This functions can be used for listing functions, classes and
    data defined in a file.  This can be useful if you want to list
    them in "sidebar".  Each element in the returned list also has
    `defined_names` method which can be used to get sub-definitions
    (e.g., methods in class).

    :rtype: list of classes.Definition
    """
    parser = Parser(
        common.source_to_unicode(source, encoding),
        module_path=path,
    )
    return classes.defined_names(Evaluator(), parser.module)


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
