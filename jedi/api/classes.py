"""
The :mod:`jedi.api.classes` module contains the return classes of the API.
These classes are the much bigger part of the whole API, because they contain
the interesting information about completion and goto operations.
"""
import warnings
from itertools import chain

from jedi._compatibility import next, unicode, use_metaclass
from jedi import settings
from jedi import common
from jedi.parser import representation as pr
from jedi.cache import underscore_memoization
from jedi.evaluate.cache import memoize_default, CachedMetaClass
from jedi.evaluate import representation as er
from jedi.evaluate import iterable
from jedi.evaluate import imports
from jedi.evaluate import compiled
from jedi.api import keywords
from jedi.evaluate.finder import get_names_of_scope


def defined_names(evaluator, scope):
    """
    List sub-definitions (e.g., methods in class).

    :type scope: Scope
    :rtype: list of Definition
    """
    # Calling get_names_of_scope doesn't make sense always. It might include
    # star imports or inherited stuff. Wanted?
    # TODO discuss!
    if isinstance(scope, pr.Module):
        pair = scope, scope.get_defined_names()
    else:
        pair = next(get_names_of_scope(evaluator, scope, star_search=False,
                                       include_builtin=False), None)
    names = pair[1] if pair else []
    names = [n for n in names if isinstance(n, pr.Import) or (len(n) == 1)]
    return [Definition(evaluator, d) for d in sorted(names, key=lambda s: s.start_pos)]


class BaseDefinition(object):
    _mapping = {
        'posixpath': 'os.path',
        'riscospath': 'os.path',
        'ntpath': 'os.path',
        'os2emxpath': 'os.path',
        'macpath': 'os.path',
        'genericpath': 'os.path',
        'posix': 'os',
        '_io': 'io',
        '_functools': 'functools',
        '_sqlite3': 'sqlite3',
        '__builtin__': '',
        'builtins': '',
    }

    _tuple_mapping = dict((tuple(k.split('.')), v) for (k, v) in {
        'argparse._ActionsContainer': 'argparse.ArgumentParser',
        '_sre.SRE_Match': 're.MatchObject',
        '_sre.SRE_Pattern': 're.RegexObject',
    }.items())

    def __init__(self, evaluator, definition, start_pos):
        self._evaluator = evaluator
        self._start_pos = start_pos
        self._definition = definition
        """
        An instance of :class:`jedi.parsing_representation.Base` subclass.
        """
        self.is_keyword = isinstance(definition, keywords.Keyword)

        # generate a path to the definition
        self._module = definition.get_parent_until()
        if self.in_builtin_module():
            self.module_path = None
        else:
            self.module_path = self._module.path
            """Shows the file path of a module. e.g. ``/usr/lib/python2.7/os.py``"""

    @property
    def start_pos(self):
        """
        .. deprecated:: 0.7.0
           Use :attr:`.line` and :attr:`.column` instead.
        .. todo:: Remove!
        """
        warnings.warn("Use line/column instead.", DeprecationWarning)
        return self._start_pos

    @property
    def type(self):
        """
        The type of the definition.

        Here is an example of the value of this attribute.  Let's consider
        the following source.  As what is in ``variable`` is unambiguous
        to Jedi, :meth:`jedi.Script.goto_definitions` should return a list of
        definition for ``sys``, ``f``, ``C`` and ``x``.

        >>> from jedi import Script
        >>> source = '''
        ... import keyword
        ...
        ... class C:
        ...     pass
        ...
        ... class D:
        ...     pass
        ...
        ... x = D()
        ...
        ... def f():
        ...     pass
        ...
        ... variable = keyword or f or C or x'''
        >>> script = Script(source, len(source.splitlines()), 3, 'example.py')
        >>> defs = script.goto_definitions()

        Before showing what is in ``defs``, let's sort it by :attr:`line`
        so that it is easy to relate the result to the source code.

        >>> defs = sorted(defs, key=lambda d: d.line)
        >>> defs                           # doctest: +NORMALIZE_WHITESPACE
        [<Definition module keyword>, <Definition class C>,
         <Definition class D>, <Definition def f>]

        Finally, here is what you can get from :attr:`type`:

        >>> defs[0].type
        'module'
        >>> defs[1].type
        'class'
        >>> defs[2].type
        'instance'
        >>> defs[3].type
        'function'

        """
        # generate the type
        stripped = self._definition
        if isinstance(stripped, compiled.CompiledObject):
            return stripped.type()
        if isinstance(stripped, er.InstanceElement):
            stripped = stripped.var
        if isinstance(stripped, pr.NamePart):
            stripped = stripped.parent
        if isinstance(stripped, pr.Name):
            stripped = stripped.parent
        return type(stripped).__name__.lower().replace('wrapper', '')

    def _path(self):
        """The module path."""
        path = []

        def insert_nonnone(x):
            if x:
                path.insert(0, x)

        if not isinstance(self._definition, keywords.Keyword):
            par = self._definition
            while par is not None:
                if isinstance(par, pr.Import):
                    insert_nonnone(par.namespace)
                    insert_nonnone(par.from_ns)
                    if par.relative_count == 0:
                        break
                with common.ignored(AttributeError):
                    path.insert(0, par.name)
                par = par.parent
        return path

    @property
    def module_name(self):
        """
        The module name.

        >>> from jedi import Script
        >>> source = 'import json'
        >>> script = Script(source, path='example.py')
        >>> d = script.goto_definitions()[0]
        >>> print(d.module_name)                       # doctest: +ELLIPSIS
        json
        """
        return str(self._module.name)

    def in_builtin_module(self):
        """Whether this is a builtin module."""
        return isinstance(self._module, compiled.CompiledObject)

    @property
    def line_nr(self):
        """
        .. deprecated:: 0.5.0
           Use :attr:`.line` instead.
        .. todo:: Remove!
        """
        warnings.warn("Use line instead.", DeprecationWarning)
        return self.line

    @property
    def line(self):
        """The line where the definition occurs (starting with 1)."""
        if self.in_builtin_module():
            return None
        return self._start_pos[0]

    @property
    def column(self):
        """The column where the definition occurs (starting with 0)."""
        if self.in_builtin_module():
            return None
        return self._start_pos[1]

    def docstring(self, raw=False):
        r"""
        Return a document string for this completion object.

        Example:

        >>> from jedi import Script
        >>> source = '''\
        ... def f(a, b=1):
        ...     "Document for function f."
        ... '''
        >>> script = Script(source, 1, len('def f'), 'example.py')
        >>> doc = script.goto_definitions()[0].docstring()
        >>> print(doc)
        f(a, b = 1)
        <BLANKLINE>
        Document for function f.

        Notice that useful extra information is added to the actual
        docstring.  For function, it is call signature.  If you need
        actual docstring, use ``raw=True`` instead.

        >>> print(script.goto_definitions()[0].docstring(raw=True))
        Document for function f.

        """
        if raw:
            return _Help(self._definition).raw()
        else:
            return _Help(self._definition).full()

    @property
    def doc(self):
        """
        .. deprecated:: 0.8.0
           Use :meth:`.docstring` instead.
        .. todo:: Remove!
        """
        warnings.warn("Use docstring() instead.", DeprecationWarning)
        return self.docstring()

    @property
    def raw_doc(self):
        """
        .. deprecated:: 0.8.0
           Use :meth:`.docstring` instead.
        .. todo:: Remove!
        """
        warnings.warn("Use docstring() instead.", DeprecationWarning)
        return self.docstring(raw=True)

    @property
    def description(self):
        """A textual description of the object."""
        return unicode(self._definition)

    @property
    def full_name(self):
        """
        Dot-separated path of this object.

        It is in the form of ``<module>[.<submodule>[...]][.<object>]``.
        It is useful when you want to look up Python manual of the
        object at hand.

        Example:

        >>> from jedi import Script
        >>> source = '''
        ... import os
        ... os.path.join'''
        >>> script = Script(source, 3, len('os.path.join'), 'example.py')
        >>> print(script.goto_definitions()[0].full_name)
        os.path.join

        Notice that it correctly returns ``'os.path.join'`` instead of
        (for example) ``'posixpath.join'``.

        """
        path = [unicode(p) for p in self._path()]
        # TODO add further checks, the mapping should only occur on stdlib.
        if not path:
            return None  # for keywords the path is empty

        with common.ignored(KeyError):
            path[0] = self._mapping[path[0]]
        for key, repl in self._tuple_mapping.items():
            if tuple(path[:len(key)]) == key:
                path = [repl] + path[len(key):]

        return '.'.join(path if path[0] else path[1:])

    @memoize_default()
    def _follow_statements_imports(self):
        """
        Follow both statements and imports, as far as possible.
        """
        stripped = self._definition
        if isinstance(stripped, pr.Name):
            stripped = stripped.parent

        # We should probably work in `Finder._names_to_types` here.
        if isinstance(stripped, pr.Function):
            stripped = er.Function(self._evaluator, stripped)
        elif isinstance(stripped, pr.Class):
            stripped = er.Class(self._evaluator, stripped)

        if stripped.isinstance(pr.Statement):
            return self._evaluator.eval_statement(stripped)
        elif stripped.isinstance(pr.Import):
            return imports.follow_imports(self._evaluator, [stripped])
        else:
            return [stripped]

    @property
    @memoize_default()
    def params(self):
        """
        Raises an ``AttributeError``if the definition is not callable.
        Otherwise returns a list of `Definition` that represents the params.
        """
        followed = self._follow_statements_imports()
        if not followed or not followed[0].is_callable():
            raise AttributeError()
        followed = followed[0]  # only check the first one.

        if followed.isinstance(er.Function):
            if isinstance(followed, er.InstanceElement):
                params = followed.params[1:]
            else:
                params = followed.params
        elif followed.isinstance(er.compiled.CompiledObject):
            params = followed.params
        else:
            try:
                sub = followed.get_subscope_by_name('__init__')
                params = sub.params[1:]  # ignore self
            except KeyError:
                return []
        return [_Param(self._evaluator, p) for p in params]

    def parent(self):
        if isinstance(self._definition, compiled.CompiledObject):
            non_flow = self._definition.parent
        else:
            scope = self._definition.get_parent_until(pr.IsScope, include_current=False)
            non_flow = scope.get_parent_until(pr.Flow, reverse=True)
        return Definition(self._evaluator, non_flow)

    def __repr__(self):
        return "<%s %s>" % (type(self).__name__, self.description)


class Completion(BaseDefinition):
    """
    `Completion` objects are returned from :meth:`api.Script.completions`. They
    provide additional information about a completion.
    """
    def __init__(self, evaluator, name, needs_dot, like_name_length, base):
        super(Completion, self).__init__(evaluator, name.parent, name.start_pos)

        self._name = name
        self._needs_dot = needs_dot
        self._like_name_length = like_name_length
        self._base = base

        # Completion objects with the same Completion name (which means
        # duplicate items in the completion)
        self._same_name_completions = []

    def _complete(self, like_name):
        dot = '.' if self._needs_dot else ''
        append = ''
        if settings.add_bracket_after_function \
                and self.type == 'Function':
            append = '('

        if settings.add_dot_after_module:
            if isinstance(self._base, pr.Module):
                append += '.'
        if isinstance(self._base, pr.Param):
            append += '='

        name = str(self._name.names[-1])
        if like_name:
            name = name[self._like_name_length:]
        return dot + name + append

    @property
    def complete(self):
        """
        Return the rest of the word, e.g. completing ``isinstance``::

            isinstan# <-- Cursor is here

        would return the string 'ce'. It also adds additional stuff, depending
        on your `settings.py`.
        """
        return self._complete(True)

    @property
    def name(self):
        """
        Similar to :attr:`complete`, but return the whole word, for
        example::

            isinstan

        would return `isinstance`.
        """
        return unicode(self._name.names[-1])

    @property
    def name_with_symbols(self):
        """
        Similar to :attr:`name`, but like :attr:`name`
        returns also the symbols, for example::

            list()

        would return ``.append`` and others (which means it adds a dot).
        """
        return self._complete(False)

    @property
    def word(self):
        """
        .. deprecated:: 0.6.0
           Use :attr:`.name` instead.
        .. todo:: Remove!
        """
        warnings.warn("Use name instead.", DeprecationWarning)
        return self.name

    @property
    def description(self):
        """Provide a description of the completion object."""
        parent = self._name.parent
        if parent is None:
            return ''
        t = self.type
        if t == 'statement' or t == 'import':
            desc = self._definition.get_code(False)
        else:
            desc = '.'.join(unicode(p) for p in self._path())

        line = '' if self.in_builtin_module else '@%s' % self.line
        return '%s: %s%s' % (t, desc, line)

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self._name)

    def docstring(self, raw=False, fast=True):
        """
        :param fast: Don't follow imports that are only one level deep like
            ``import foo``, but follow ``from foo import bar``. This makes
            sense for speed reasons. Completing `import a` is slow if you use
            the ``foo.docstring(fast=False)`` on every object, because it
            parses all libraries starting with ``a``.
        """
        definition = self._definition
        if isinstance(self._definition, pr.Import):
            i = imports.ImportWrapper(self._evaluator, self._definition)
            if len(i.import_path) > 1 or not fast:
                followed = self._follow_statements_imports()
                if followed:
                    # TODO: Use all of the followed objects as input to Documentation.
                    definition = followed[0]

        if raw:
            return _Help(definition).raw()
        else:
            return _Help(definition).full()

    @property
    def type(self):
        """
        The type of the completion objects. Follows imports. For a further
        description, look at :attr:`jedi.api.classes.BaseDefinition.type`.
        """
        if isinstance(self._definition, pr.Import):
            i = imports.ImportWrapper(self._evaluator, self._definition)
            if len(i.import_path) <= 1:
                return 'module'

            followed = self.follow_definition()
            if followed:
                # Caveat: Only follows the first one, ignore the other ones.
                # This is ok, since people are almost never interested in
                # variations.
                return followed[0].type
        return super(Completion, self).type

    @memoize_default()
    def _follow_statements_imports(self):
        # imports completion is very complicated and needs to be treated
        # separately in Completion.
        if self._definition.isinstance(pr.Import) and self._definition.alias is None:
            i = imports.ImportWrapper(self._evaluator, self._definition, True)
            import_path = i.import_path + (unicode(self._name),)
            try:
                return imports.get_importer(self._evaluator, import_path,
                                            i._importer.module).follow(self._evaluator)
            except imports.ModuleNotFound:
                pass
        return super(Completion, self)._follow_statements_imports()

    @memoize_default()
    def follow_definition(self):
        """
        Return the original definitions. I strongly recommend not using it for
        your completions, because it might slow down |jedi|. If you want to
        read only a few objects (<=20), it might be useful, especially to get
        the original docstrings. The basic problem of this function is that it
        follows all results. This means with 1000 completions (e.g.  numpy),
        it's just PITA-slow.
        """
        defs = self._follow_statements_imports()
        return [Definition(self._evaluator, d) for d in defs]


class Definition(use_metaclass(CachedMetaClass, BaseDefinition)):
    """
    *Definition* objects are returned from :meth:`api.Script.goto_assignments`
    or :meth:`api.Script.goto_definitions`.
    """
    def __init__(self, evaluator, definition):
        super(Definition, self).__init__(evaluator, definition, definition.start_pos)

    @property
    @underscore_memoization
    def name(self):
        """
        Name of variable/function/class/module.

        For example, for ``x = None`` it returns ``'x'``.

        :rtype: str or None
        """
        d = self._definition
        if isinstance(d, er.InstanceElement):
            d = d.var

        if isinstance(d, (compiled.CompiledObject, compiled.CompiledName)):
            name = d.name
        elif isinstance(d, pr.Name):
            name = d.names[-1]
        elif isinstance(d, iterable.Array):
            name = d.type
        elif isinstance(d, (pr.Class, er.Class, er.Instance,
                            er.Function, pr.Function)):
            name = d.name
        elif isinstance(d, pr.Module):
            name = self.module_name
        elif isinstance(d, pr.Import):
            try:
                name = d.get_defined_names()[0].names[-1]
            except (AttributeError, IndexError):
                return None
        elif isinstance(d, pr.Param):
            name = d.get_name()
        elif isinstance(d, pr.Statement):
            try:
                expression_list = d.assignment_details[0][0]
                name = expression_list[0].name.names[-1]
            except IndexError:
                return None
        elif isinstance(d, iterable.Generator):
            return None
        elif isinstance(d, pr.NamePart):
            name = d
        return unicode(name)

    @property
    def description(self):
        """
        A description of the :class:`.Definition` object, which is heavily used
        in testing. e.g. for ``isinstance`` it returns ``def isinstance``.

        Example:

        >>> from jedi import Script
        >>> source = '''
        ... def f():
        ...     pass
        ...
        ... class C:
        ...     pass
        ...
        ... variable = f or C'''
        >>> script = Script(source, column=3)  # line is maximum by default
        >>> defs = script.goto_definitions()
        >>> defs = sorted(defs, key=lambda d: d.line)
        >>> defs
        [<Definition def f>, <Definition class C>]
        >>> str(defs[0].description)  # strip literals in python2
        'def f'
        >>> str(defs[1].description)
        'class C'

        """
        d = self._definition
        if isinstance(d, er.InstanceElement):
            d = d.var
        if isinstance(d, pr.Name):
            d = d.parent

        if isinstance(d, compiled.CompiledObject):
            d = d.type() + ' ' + d.name
        elif isinstance(d, iterable.Array):
            d = 'class ' + d.type
        elif isinstance(d, (pr.Class, er.Class, er.Instance)):
            d = 'class ' + unicode(d.name)
        elif isinstance(d, (er.Function, pr.Function)):
            d = 'def ' + unicode(d.name)
        elif isinstance(d, pr.Module):
            # only show module name
            d = 'module %s' % self.module_name
        elif self.is_keyword:
            d = 'keyword %s' % d.name
        else:
            d = d.get_code().replace('\n', '').replace('\r', '')
        return d

    @property
    def desc_with_module(self):
        """
        In addition to the definition, also return the module.

        .. warning:: Don't use this function yet, its behaviour may change. If
            you really need it, talk to me.

        .. todo:: Add full path. This function is should return a
            `module.class.function` path.
        """
        position = '' if self.in_builtin_module else '@%s' % (self.line)
        return "%s:%s%s" % (self.module_name, self.description, position)

    @memoize_default()
    def defined_names(self):
        """
        List sub-definitions (e.g., methods in class).

        :rtype: list of Definition
        """
        defs = self._follow_statements_imports()
        # For now we don't want base classes or evaluate decorators.
        defs = [d.base if isinstance(d, (er.Class, er.Function)) else d for d in defs]
        iterable = (defined_names(self._evaluator, d) for d in defs)
        iterable = list(iterable)
        return list(chain.from_iterable(iterable))

    def __eq__(self, other):
        return self._start_pos == other._start_pos \
            and self.module_path == other.module_path \
            and self.name == other.name \
            and self._evaluator == other._evaluator

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self._start_pos, self.module_path, self.name, self._evaluator))


class CallSignature(Definition):
    """
    `CallSignature` objects is the return value of `Script.function_definition`.
    It knows what functions you are currently in. e.g. `isinstance(` would
    return the `isinstance` function. without `(` it would return nothing.
    """
    def __init__(self, evaluator, executable, call, index, key_name):
        super(CallSignature, self).__init__(evaluator, executable)
        self._index = index
        self._key_name = key_name
        self._call = call

    @property
    def index(self):
        """
        The Param index of the current call.
        Returns None if the index doesn't is not defined.
        """
        if self._key_name is not None:
            for i, param in enumerate(self.params):
                if self._key_name == param.name:
                    return i
            if self.params and self.params[-1]._definition.stars == 2:
                return i
            else:
                return None

        if self._index >= len(self.params):

            for i, param in enumerate(self.params):
                # *args case
                if param._definition.stars == 1:
                    return i
            return None
        return self._index

    @property
    def bracket_start(self):
        """
        The indent of the bracket that is responsible for the last function
        call.
        """
        c = self._call
        while c.next is not None:
            c = c.next
        return c.name.end_pos

    @property
    def call_name(self):
        """
        .. deprecated:: 0.8.0
           Use :attr:`.name` instead.
        .. todo:: Remove!

        The name (e.g. 'isinstance') as a string.
        """
        warnings.warn("Use name instead.", DeprecationWarning)
        return unicode(self._definition.name)

    @property
    def module(self):
        """
        .. deprecated:: 0.8.0
           Use :attr:`.module_name` for the module name.
        .. todo:: Remove!
        """
        return self._executable.get_parent_until()

    def __repr__(self):
        return '<%s: %s index %s>' % (type(self).__name__, self._definition,
                                      self.index)


class _Param(Definition):
    """
    Just here for backwards compatibility.
    """
    def get_code(self):
        """
        .. deprecated:: 0.8.0
           Use :attr:`.description` and :attr:`.name` instead.
        .. todo:: Remove!

        A function to get the whole code of the param.
        """
        warnings.warn("Use description instead.", DeprecationWarning)
        return self.description


class _Help(object):
    """
    Temporary implementation, will be used as `Script.help() or something in
    the future.
    """
    def __init__(self, definition):
        self._definition = definition

    def full(self):
        try:
            return self._definition.doc
        except AttributeError:
            return self.raw()

    def raw(self):
        """
        The raw docstring ``__doc__`` for any object.

        See :attr:`doc` for example.
        """
        try:
            return self._definition.raw_doc
        except AttributeError:
            return ''
