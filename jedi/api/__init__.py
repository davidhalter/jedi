"""
The API basically only provides one class. You can create a :class:`Script` and
use its methods.

Additionally you can add a debug function with :func:`set_debug_function`.

.. warning:: Please, note that Jedi is **not thread safe**.
"""
import re
import os
import warnings
import sys
import collections

from jedi._compatibility import unicode
from jedi.parser import load_grammar
from jedi.parser import tree
from jedi.parser.user_context import UserContext, UserContextParser
from jedi import debug
from jedi import settings
from jedi import common
from jedi import cache
from jedi.api import classes
from jedi.api import interpreter
from jedi.api import usages
from jedi.api import helpers
from jedi.api import inference
from jedi.api.completion import Completion
from jedi.evaluate import Evaluator
from jedi.evaluate import representation as er
from jedi.evaluate import imports
from jedi.evaluate.param import try_iter_content
from jedi.evaluate.helpers import get_module_names
from jedi.evaluate.sys_path import get_venv_path
from jedi.evaluate.iterable import unpack_tuple_to_dict

# Jedi uses lots and lots of recursion. By setting this a little bit higher, we
# can remove some "maximum recursion depth" errors.
sys.setrecursionlimit(2000)


class NotFoundError(Exception):
    """A custom error to avoid catching the wrong exceptions.

    .. deprecated:: 0.9.0
       Not in use anymore, Jedi just returns no goto result if you're not on a
       valid name.
    .. todo:: Remove!
    """


class Script(object):
    """
    A Script is the base for completions, goto or whatever you want to do with
    |jedi|.

    You can either use the ``source`` parameter or ``path`` to read a file.
    Usually you're going to want to use both of them (in an editor).

    The script might be analyzed in a different ``sys.path`` than |jedi|:

    - if `sys_path` parameter is not ``None``, it will be used as ``sys.path``
      for the script;

    - if `sys_path` parameter is ``None`` and ``VIRTUAL_ENV`` environment
      variable is defined, ``sys.path`` for the specified environment will be
      guessed (see :func:`jedi.evaluate.sys_path.get_venv_path`) and used for
      the script;

    - otherwise ``sys.path`` will match that of |jedi|.

    :param source: The source code of the current file, separated by newlines.
    :type source: str
    :param line: The line to perform actions on (starting with 1).
    :type line: int
    :param column: The column of the cursor (starting with 0).
    :type column: int
    :param path: The path of the file in the file system, or ``''`` if
        it hasn't been saved yet.
    :type path: str or None
    :param encoding: The encoding of ``source``, if it is not a
        ``unicode`` object (default ``'utf-8'``).
    :type encoding: str
    :param source_encoding: The encoding of ``source``, if it is not a
        ``unicode`` object (default ``'utf-8'``).
    :type encoding: str
    :param sys_path: ``sys.path`` to use during analysis of the script
    :type sys_path: list

    """
    def __init__(self, source=None, line=None, column=None, path=None,
                 encoding='utf-8', source_path=None, source_encoding=None,
                 sys_path=None):
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
        self._grammar = load_grammar(version='%s.%s' % sys.version_info[:2])
        self._user_context = UserContext(self.source, self._pos)
        self._parser = UserContextParser(self._grammar, self.source, path,
                                         self._pos, self._user_context,
                                         self._parsed_callback)
        if sys_path is None:
            venv = os.getenv('VIRTUAL_ENV')
            if venv:
                sys_path = list(get_venv_path(venv))
        self._evaluator = Evaluator(self._grammar, sys_path=sys_path)
        debug.speed('init')

    def _parsed_callback(self, parser):
        module = self._evaluator.wrap(parser.module)
        imports.add_module(self._evaluator, unicode(module.name), module)

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
        debug.speed('completions start')
        path = self._user_context.get_path_until_cursor()
        completion = Completion(
            self._evaluator, self._parser, self._user_context,
            self._pos, self.call_signatures
        )
        completions = completion.completions(path)
        debug.speed('completions end')
        return completions

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
        def resolve_import_paths(definitions):
            new_defs = list(definitions)
            for s in definitions:
                if isinstance(s, imports.ImportWrapper):
                    new_defs.remove(s)
                    new_defs += resolve_import_paths(set(s.follow()))
            return new_defs

        goto_path = self._user_context.get_path_under_cursor()
        context = self._user_context.get_reverse_context()
        definitions = []
        if next(context) in ('class', 'def'):
            definitions = [self._evaluator.wrap(self._parser.user_scope())]
        else:
            # Fetch definition of callee, if there's no path otherwise.
            if not goto_path:
                definitions = [signature._definition
                               for signature in self.call_signatures()]

        if re.match('\w[\w\d_]*$', goto_path) and not definitions:
            user_stmt = self._parser.user_stmt()
            if user_stmt is not None and user_stmt.type == 'expr_stmt':
                for name in user_stmt.get_defined_names():
                    if name.start_pos <= self._pos <= name.end_pos:
                        # TODO scaning for a name and then using it should be
                        # the default.
                        definitions = self._evaluator.goto_definition(name)

        if not definitions and goto_path:
            definitions = inference.type_inference(
                self._evaluator, self._parser, self._user_context,
                self._pos, goto_path
            )

        definitions = resolve_import_paths(definitions)
        names = [s.name for s in definitions]
        defs = [classes.Definition(self._evaluator, name) for name in names]
        # The additional set here allows the definitions to become unique in an
        # API sense. In the internals we want to separate more things than in
        # the API.
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
        d = [classes.Definition(self._evaluator, d) for d in set(results)]
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
                if isinstance(d.parent, tree.Import) \
                        and d.start_pos == (0, 0):
                    i = imports.ImportWrapper(self._evaluator, d.parent).follow(is_goto=True)
                    definitions.remove(d)
                    definitions |= follow_inexistent_imports(i)
            return definitions

        goto_path = self._user_context.get_path_under_cursor()
        context = self._user_context.get_reverse_context()
        user_stmt = self._parser.user_stmt()
        user_scope = self._parser.user_scope()

        stmt = inference.get_under_cursor_stmt(self._evaluator, self._parser,
                                               goto_path, self._pos)
        if stmt is None:
            return []

        if user_scope is None:
            last_name = None
        else:
            # Try to use the parser if possible.
            last_name = user_scope.name_for_position(self._pos)

        if last_name is None:
            last_name = stmt
            while not isinstance(last_name, tree.Name):
                try:
                    last_name = last_name.children[-1]
                except AttributeError:
                    # Doesn't have a name in it.
                    return []

        if next(context) in ('class', 'def'):
            # The cursor is on a class/function name.
            definitions = set([user_scope.name])
        elif isinstance(user_stmt, tree.Import):
            s, name = helpers.get_on_import_stmt(self._evaluator,
                                                 self._user_context, user_stmt)

            definitions = self._evaluator.goto(name)
        else:
            # The Evaluator.goto function checks for definitions, but since we
            # use a reverse tokenizer, we have new name_part objects, so we
            # have to check the user_stmt here for positions.
            if isinstance(user_stmt, tree.ExprStmt) \
                    and isinstance(last_name.parent, tree.ExprStmt):
                for name in user_stmt.get_defined_names():
                    if name.start_pos <= self._pos <= name.end_pos:
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
            if not definitions and isinstance(user_stmt, tree.Import):
                # For not defined imports (goto doesn't find something, we take
                # the name as a definition. This is enough, because every name
                # points to it.
                name = user_stmt.name_for_position(self._pos)
                if name is None:
                    # Must be syntax
                    return []
                definitions = [name]

            if not definitions:
                # Without a definition for a name we cannot find references.
                return []

            if not isinstance(user_stmt, tree.Import):
                # import case is looked at with add_import_name option
                definitions = usages.usages_add_import_modules(self._evaluator,
                                                               definitions)

            module = set([d.get_parent_until() for d in definitions])
            module.add(self._parser.module())
            names = usages.usages(self._evaluator, definitions, module)

            for d in set(definitions):
                names.append(classes.Definition(self._evaluator, d))
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
        call_txt, call_index, key_name, start_pos = self._user_context.call_signature()
        if call_txt is None:
            return []

        stmt = inference.get_under_cursor_stmt(self._evaluator, self._parser,
                                               call_txt, start_pos)
        if stmt is None:
            return []

        with common.scale_speed_settings(settings.scale_call_signatures):
            origins = cache.cache_call_signatures(self._evaluator, stmt,
                                                  self.source, self._pos)
        debug.speed('func_call followed')

        return [classes.CallSignature(self._evaluator, o.name, stmt, call_index, key_name)
                for o in origins if hasattr(o, 'py__call__')]

    def _analysis(self):
        self._evaluator.is_analysis = True
        self._evaluator.analysis_modules = [self._parser.module()]
        try:
            for node in self._parser.module().nodes_to_execute():
                if node.type in ('funcdef', 'classdef'):
                    if node.type == 'classdef':
                        continue
                        raise NotImplementedError
                    er.Function(self._evaluator, node).get_decorated_func()
                elif isinstance(node, tree.Import):
                    import_names = set(node.get_defined_names())
                    if node.is_nested():
                        import_names |= set(path[-1] for path in node.paths())
                    for n in import_names:
                        imports.ImportWrapper(self._evaluator, n).follow()
                elif node.type == 'expr_stmt':
                    types = self._evaluator.eval_element(node)
                    for testlist in node.children[:-1:2]:
                        # Iterate tuples.
                        unpack_tuple_to_dict(self._evaluator, types, testlist)
                else:
                    try_iter_content(self._evaluator.goto_definition(node))
                self._evaluator.reset_recursion_limitations()

            ana = [a for a in self._evaluator.analysis if self.path == a.path]
            return sorted(set(ana), key=lambda x: x.line)
        finally:
            self._evaluator.is_analysis = False


class Interpreter(Script):
    """
    Jedi API for Python REPLs.

    In addition to completion of simple attribute access, Jedi
    supports code completion based on static code analysis.
    Jedi can complete attributes of object which is not initialized
    yet.

    >>> from os.path import join
    >>> namespace = locals()
    >>> script = Interpreter('join("").up', [namespace])
    >>> print(script.completions()[0].name)
    upper
    """

    def __init__(self, source, namespaces, **kwds):
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
        if type(namespaces) is not list or len(namespaces) == 0 or \
                not all(isinstance(x, collections.Mapping) for x in namespaces):
            raise TypeError("namespaces must be a non-empty list of dicts.")

        super(Interpreter, self).__init__(source, **kwds)
        self.namespaces = namespaces

        # Don't use the fast parser, because it does crazy stuff that we don't
        # need in our very simple and small code here (that is always
        # changing).
        self._parser = UserContextParser(self._grammar, self.source,
                                         self._orig_path, self._pos,
                                         self._user_context, self._parsed_callback,
                                         use_fast_parser=False)
        interpreter.add_namespaces_to_parser(self._evaluator, namespaces,
                                             self._parser.module())


def defined_names(source, path=None, encoding='utf-8'):
    """
    Get all definitions in `source` sorted by its position.

    This functions can be used for listing functions, classes and
    data defined in a file.  This can be useful if you want to list
    them in "sidebar".  Each element in the returned list also has
    `defined_names` method which can be used to get sub-definitions
    (e.g., methods in class).

    :rtype: list of classes.Definition

    .. deprecated:: 0.9.0
       Use :func:`names` instead.
    .. todo:: Remove!
    """
    warnings.warn("Use call_signatures instead.", DeprecationWarning)
    return names(source, path, encoding)


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
            for name_part in get_module_names(script._parser.module(), all_scopes)]
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
