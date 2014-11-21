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
from jedi.evaluate import Evaluator
from jedi.evaluate import representation as er
from jedi.evaluate import compiled
from jedi.evaluate import imports
from jedi.evaluate.helpers import FakeName, get_module_name_parts
from jedi.evaluate.finder import get_names_of_scope, filter_private_variable
from jedi.evaluate.helpers import search_call_signatures
from jedi.evaluate import analysis

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

        self.source = common.source_to_unicode(source, encoding)
        lines = common.splitlines(self.source)
        line = max(len(lines), 1) if line is None else line
        if not (0 < line <= len(lines)):
            raise ValueError('`line` parameter is not in a valid range.')

        line_len = len(lines[line - 1])
        column = line_len if column is None else column
        if not (0 <= column <= line_len):
            raise ValueError('`column` parameter is not in a valid range.')
        self._pos = line, column

        cache.clear_time_caches()
        debug.reset_time()
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
                # Allow protected access, because it's a public API.
                module = call_sig._name.get_parent_until()
                # Compiled modules typically don't allow keyword arguments.
                if not isinstance(module, compiled.CompiledObject):
                    for p in call_sig.params:
                        # Allow access on _definition here, because it's a
                        # public API and we don't want to make the internal
                        # Name object public.
                        if p._definition.stars == 0:  # no *args/**kwargs
                            completions.append((p._name, p._name))

            if not path and not isinstance(user_stmt, pr.Import):
                # add keywords
                completions += ((k, b) for k in keywords.keyword_names(all=True))

        needs_dot = not dot and path

        comps = []
        comp_dct = {}
        for c, s in set(completions):
            n = str(c)
            if settings.case_insensitive_completion \
                    and n.lower().startswith(like.lower()) \
                    or n.startswith(like):
                if not filter_private_variable(s, user_stmt or self._parser.user_scope(), n):
                    if isinstance(c.parent, (pr.Function, pr.Class)):
                        # TODO I think this is a hack. It should be an
                        #   er.Function/er.Class before that.
                        c = er.wrap(self._evaluator, c.parent).name
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
            scope_names_generator = get_names_of_scope(self._evaluator,
                                                       self._parser.user_scope(),
                                                       self._pos)
            completions = []
            for scope, name_list in scope_names_generator:
                for c in name_list:
                    completions.append((c, scope))
        else:
            completions = []
            debug.dbg('possible completion scopes: %s', scopes)
            for s in scopes:
                if s.isinstance(er.Function):
                    names = s.get_magic_function_names()
                elif isinstance(s, imports.ImportWrapper):
                    under = like + self._user_context.get_path_after_cursor()
                    if under == 'import':
                        current_line = self._user_context.get_position_line()
                        if not current_line.endswith('import import'):
                            continue
                    """
                    a = s.import_stmt.alias
                    if a and a.start_pos <= self._pos <= a.end_pos:
                        continue
                    """
                    # TODO what to do with this?
                    names = s.get_defined_names(on_import_stmt=True)
                else:
                    names = []
                    for _, new_names in s.scope_names_generator():
                        names += new_names

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
                # "pseudo" statement, the Jedi evaluator can find the assignees.
                
                # TODO remove?
                if False and user_stmt is not None:
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
        if not isinstance(stmt, (pr.ExprStmt, pr.KeywordStatement)):
            raise NotFoundError()

        user_stmt = self._parser.user_stmt()
        if user_stmt is None:
            # Set the start_pos to a pseudo position, that doesn't exist but works
            # perfectly well (for both completions in docstrings and statements).
            pos = self._pos
        else:
            pos = user_stmt.start_pos

        stmt.move(pos[0] - 1, pos[1])
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
        warnings.warn("Use call_signatures instead.", DeprecationWarning)
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
            definitions = set([er.wrap(self._evaluator, self._parser.user_scope())])
        else:
            # Fetch definition of callee, if there's no path otherwise.
            if not goto_path:
                call, _, _ = search_call_signatures(user_stmt, self._pos)
                if call is not None:
                    definitions = set(self._evaluator.eval_call(call))

        if not definitions:
            if goto_path:
                definitions = set(self._prepare_goto(goto_path))

        definitions = resolve_import_paths(definitions)
        names = [s.name for s in definitions
                 if s is not imports.ImportWrapper.GlobalNamespace]
        defs = [classes.Definition(self._evaluator, name) for name in names]
        return helpers.sorted_definitions(set(defs))

    def goto_assignments(self):
        """
        Return the first definition found. Imports and statements aren't
        followed. Multiple objects may be returned, because Python itself is a
        dynamic language, which means depending on an option you can have two
        different versions of a function.

        :rtype: list of :class:`classes.Definition`
        """
        results = self._goto()
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

        stmt = self._get_under_cursor_stmt(goto_path)
        if stmt is None:
            return []

        last_name = stmt
        while not isinstance(last_name, pr.Name):
            last_name = last_name.children[-1]

        if next(context) in ('class', 'def'):
            # The cursor is on a class/function name.
            user_scope = self._parser.user_scope()
            definitions = set([user_scope.name])
        elif isinstance(user_stmt, pr.Import):
            s, name_part = helpers.get_on_import_stmt(self._evaluator,
                                                      self._user_context, user_stmt)
            try:
                definitions = [s.follow(is_goto=True)[0]]
            except IndexError:
                definitions = []

            if add_import_name:
                import_name = user_stmt.get_defined_names()
                # imports have only one name
                np = import_name[0]
                if not user_stmt.star and unicode(name_part) == unicode(np):
                    definitions.append(np)
        else:
            # The Evaluator.goto function checks for definitions, but since we
            # use a reverse tokenizer, we have new name_part objects, so we
            # have to check the user_stmt here for positions.
            if     False and     isinstance(user_stmt, pr.ExprStmt):
                for name in user_stmt.get_defined_names():
                    if name.start_pos <= self._pos <= name.end_pos \
                            and (not isinstance(name.parent, pr.Call)
                                 or name.parent.next is None):
                        return [name]

            defs = self._evaluator.goto(last_name)
            definitions = follow_inexistent_imports(defs)
        return definitions

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
        try:
            user_stmt = self._parser.user_stmt()
            definitions = self._goto(add_import_name=True)
            if not definitions:
                # Without a definition for a name we cannot find references.
                return []

            if not isinstance(user_stmt, pr.Import):
                # import case is looked at with add_import_name option
                definitions = usages.usages_add_import_modules(self._evaluator,
                                                               definitions)

            module = set([d.get_parent_until() for d in definitions])
            module.add(self._parser.module())
            names = usages.usages(self._evaluator, definitions, module)

            for d in set(definitions):
                try:
                    name_part = d.names[-1]
                except AttributeError:
                    names.append(classes.Definition(self._evaluator, d))
                else:
                    names.append(classes.Definition(self._evaluator, name_part))
        finally:
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
        call, execution_arr, index = search_call_signatures(user_stmt, self._pos)
        if call is None:
            return []

        with common.scale_speed_settings(settings.scale_call_signatures):
            origins = cache.cache_call_signatures(self._evaluator, call, self.source,
                                                  self._pos, user_stmt)
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
        return [classes.CallSignature(self._evaluator, o.name, call, index, key_name)
                for o in origins if hasattr(o, 'py__call__')]

    def _analysis(self):
        #statements = set(chain(*self._parser.module().used_names.values()))
        stmts, imps = analysis.get_module_statements(self._parser.module())
        # Sort the statements so that the results are reproducible.
        for i in imps:
            iw = imports.ImportWrapper(self._evaluator, i,
                                       nested_resolve=True).follow()
            if i.is_nested() and any(not isinstance(i, pr.Module) for i in iw):
                analysis.add(self._evaluator, 'import-error', i.namespace_names[-1])
        for stmt in sorted(stmts, key=lambda obj: obj.start_pos):
            if not (isinstance(stmt.parent, pr.ForFlow)
                    and stmt.parent.set_stmt == stmt):
                self._evaluator.eval_statement(stmt)

        ana = [a for a in self._evaluator.analysis if self.path == a.path]
        return sorted(set(ana), key=lambda x: x.line)


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
            return super(Interpreter, self)._simple_complete(path, like)
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
                    gen = (n.keys() for n in self.namespaces)
                    return list(set(chain.from_iterable(gen)))

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


def names(source=None, path=None, encoding='utf-8', all_scopes=False,
          definitions=True, references=False):
    """
    Returns a list of `Definition` objects, containing name parts.
    This means you can call ``Definition.goto_assignments()`` and get the
    reference of a name.
    The parameters are the same as in :py:class:`Script`, except or the
    following ones:

    :param all_scopes: If True lists the names of all scopes instead of only
        the module namespace.
    :param definitions: If True lists the names that have been defined by a
        class, function or a statement (``a = b`` returns ``a``).
    :param references: If True lists all the names that are not listed by
        ``definitions=True``. E.g. ``a = b`` returns ``b``.
    """
    def def_ref_filter(_def):
        is_def = _def.is_definition()
        return definitions and is_def or references and not is_def

    # Set line/column to a random position, because they don't matter.
    script = Script(source, line=1, column=0, path=path, encoding=encoding)
    defs = [classes.Definition(script._evaluator, name_part)
            for name_part in get_module_name_parts(script._parser.module())]
    return sorted(filter(def_ref_filter, defs), key=lambda x: (x.line, x.column))


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
