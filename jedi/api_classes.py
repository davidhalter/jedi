"""
The :mod:`api_classes` module contains the return classes of the API. These
classes are the much bigger part of the whole API, because they contain the
interesting information about completion and goto operations.
"""

import re
import os
import warnings

from _compatibility import unicode
import cache
import dynamic
import helpers
import settings
import evaluate
import imports
import parsing
import keywords


def _clear_caches():
    """
    Clear all caches of this and related modules. The only cache that will not
    be deleted is the module cache.
    """
    cache.clear_caches()
    dynamic.search_param_cache.clear()
    helpers.ExecutionRecursionDecorator.reset()

    evaluate.follow_statement.reset()

    imports.imports_processed = 0


class BaseDefinition(object):
    _mapping = {'posixpath': 'os.path',
               'riscospath': 'os.path',
               'ntpath': 'os.path',
               'os2emxpath': 'os.path',
               'macpath': 'os.path',
               'genericpath': 'os.path',
               '_io': 'io',
               '__builtin__': '',
               'builtins': '',
               }

    _tuple_mapping = dict((tuple(k.split('.')), v) for (k, v) in {
        'argparse._ActionsContainer': 'argparse.ArgumentParser',
        '_sre.SRE_Match': 're.MatchObject',
        '_sre.SRE_Pattern': 're.RegexObject',
    }.items())

    def __init__(self, definition, start_pos):
        self.start_pos = start_pos
        self.definition = definition
        self.is_keyword = isinstance(definition, keywords.Keyword)

        # generate a path to the definition
        self.module_path = unicode(definition.get_parent_until().path)

    @property
    def type(self):
        """The type of the definition."""
        # generate the type
        stripped = self.definition
        if isinstance(self.definition, evaluate.InstanceElement):
            stripped = self.definition.var
        return type(stripped).__name__

    @property
    def path(self):
        """The module path."""
        path = []
        if not isinstance(self.definition, keywords.Keyword):
            par = self.definition
            while par is not None:
                try:
                    path.insert(0, par.name)
                except AttributeError:
                    pass
                par = par.parent
        return path

    @property
    def module_name(self):
        """The module name."""
        path = self.module_path
        sep = os.path.sep
        p = re.sub(r'^.*?([\w\d]+)(%s__init__)?.py$' % sep, r'\1', path)
        return p

    def in_builtin_module(self):
        """Whether this is a builtin module."""
        return not self.module_path.endswith('.py')

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
        return self.start_pos[0]

    @property
    def column(self):
        """The column where the definition occurs (starting with 0)."""
        return self.start_pos[1]

    @property
    def doc(self):
        """Return a document string for this completion object."""
        try:
            return self.definition.doc
        except AttributeError:
            return self.raw_doc

    @property
    def raw_doc(self):
        """The raw docstring ``__doc__`` for any object."""
        try:
            return unicode(self.definition.docstr)
        except AttributeError:
            return ''

    @property
    def description(self):
        """A textual description of the object."""
        return unicode(self.definition)

    @property
    def full_name(self):
        """The path to a certain class/function, see #61."""
        path = [unicode(p) for p in self.path]
        # TODO add further checks, the mapping should only occur on stdlib.
        if not path:
            return None  # for keywords the path is empty

        try:
            path[0] = self._mapping[path[0]]
        except KeyError:
            pass
        for key, repl in self._tuple_mapping.items():
            if tuple(path[:len(key)]) == key:
                path = [repl] + path[len(key):]

        return '.'.join(path if path[0] else path[1:])

    def __repr__(self):
        return "<%s %s>" % (type(self).__name__, self.description)


class Completion(BaseDefinition):
    """
    `Completion` objects are returned from :meth:`api.Script.complete`. They
    provide additional information about a completion.
    """
    def __init__(self, name, needs_dot, like_name_length, base):
        super(Completion, self).__init__(name.parent, name.start_pos)

        self.name = name
        self.needs_dot = needs_dot
        self.like_name_length = like_name_length
        self.base = base

        # Completion objects with the same Completion name (which means
        # duplicate items in the completion)
        self._same_name_completions = []

        self._followed_definitions = None

    @property
    def complete(self):
        """
        Return the rest of the word, e.g. completing ``isinstance``::

            >>> isinstan# <-- Cursor is here

        would return the string 'ce'. It also adds additional stuff, depending
        on your `settings.py`.
        """
        dot = '.' if self.needs_dot else ''
        append = ''
        if settings.add_bracket_after_function \
                    and self.type == 'Function':
            append = '('

        if settings.add_dot_after_module:
            if isinstance(self.base, parsing.Module):
                append += '.'
        if isinstance(self.base, parsing.Param):
            append += '='
        return dot + self.name.names[-1][self.like_name_length:] + append

    @property
    def word(self):
        """
        Similar to :meth:`Completion.complete`, but return the whole word, e.g. ::

            >>> isinstan

        would return 'isinstance'.
        """
        return unicode(self.name.names[-1])

    @property
    def description(self):
        """
        Provide a description of the completion object.

        .. todo:: return value is just __repr__ of some objects, improve!
        """
        parent = self.name.parent
        if parent is None:
            return ''
        t = self.type
        if t == 'Statement' or t == 'Import':
            desc = self.definition.get_code(False)
        else:
            desc = '.'.join(unicode(p) for p in self.path)

        line = '' if self.in_builtin_module else '@%s' % self.line
        return '%s: %s%s' % (t, desc, line)

    def follow_definition(self):
        """
        Return the original definitions. I strongly recommend not using it for
        your completions, because it might slow down |jedi|. If you want to read
        only a few objects (<=20), it might be useful, especially to
        get the original docstrings. The basic problem of this function is
        that it follows all results. This means with 1000 completions (e.g.
        numpy), it's just PITA-slow.
        """
        if self._followed_definitions is None:
            if self.definition.isinstance(parsing.Statement):
                defs = evaluate.follow_statement(self.definition)
            elif self.definition.isinstance(parsing.Import):
                defs = imports.strip_imports([self.definition])
            else:
                return [self]

            self._followed_definitions = \
                            [BaseDefinition(d, d.start_pos) for d in defs]
            _clear_caches()

        return self._followed_definitions

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.name)


class Definition(BaseDefinition):
    """
    *Definition* objects are returned from :meth:`api.Script.goto` or
    :meth:`api.Script.get_definition`.
    """
    def __init__(self, definition):
        super(Definition, self).__init__(definition, definition.start_pos)

    @property
    def description(self):
        """
        A description of the :class:`.Definition` object, which is heavily used
        in testing. e.g. for ``isinstance`` it returns ``def isinstance``.
        """
        d = self.definition
        if isinstance(d, evaluate.InstanceElement):
            d = d.var
        if isinstance(d, evaluate.parsing.Name):
            d = d.parent

        if isinstance(d, evaluate.Array):
            d = 'class ' + d.type
        elif isinstance(d, (parsing.Class, evaluate.Class, evaluate.Instance)):
            d = 'class ' + unicode(d.name)
        elif isinstance(d, (evaluate.Function, evaluate.parsing.Function)):
            d = 'def ' + unicode(d.name)
        elif isinstance(d, evaluate.parsing.Module):
            # only show module name
            d = 'module %s' % self.module_name
        elif self.is_keyword:
            d = 'keyword %s' % d.name
        else:
            d = d.get_code().replace('\n', '')
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
        if self.module_path.endswith('.py') \
                    and not isinstance(self.definition, parsing.Module):
            position = '@%s' % (self.line)
        else:
            # is a builtin or module
            position = ''
        return "%s:%s%s" % (self.module_name, self.description, position)


class RelatedName(BaseDefinition):
    """TODO: document this"""
    def __init__(self, name_part, scope):
        super(RelatedName, self).__init__(scope, name_part.start_pos)
        self.name_part = name_part
        self.text = unicode(name_part)
        self.end_pos = name_part.end_pos

    @property
    def description(self):
        return "%s@%s,%s" % (self.text, self.start_pos[0], self.start_pos[1])

    def __eq__(self, other):
        return self.start_pos == other.start_pos \
            and self.module_path == other.module_path

    def __hash__(self):
        return hash((self.start_pos, self.module_path))


class CallDef(object):
    """ `CallDef` objects is the return value of `Script.get_in_function_call`.
    It knows what functions you are currently in. e.g. `isinstance(` would
    return the `isinstance` function. without `(` it would return nothing."""
    def __init__(self, executable, index, call):
        self.executable = executable
        self.index = index
        self.call = call

    @property
    def params(self):
        if self.executable.isinstance(evaluate.Function):
            if isinstance(self.executable, evaluate.InstanceElement):
                return self.executable.params[1:]
            return self.executable.params
        else:
            try:
                sub = self.executable.get_subscope_by_name('__init__')
                return sub.params[1:]  # ignore self
            except KeyError:
                return []

    @property
    def bracket_start(self):
        """ The indent of the bracket that is responsible for the last function
        call. """
        c = self.call
        while c.next is not None:
            c = c.next
        return c.name.end_pos

    @property
    def call_name(self):
        """ The name (e.g. 'isinstance') as a string. """
        return unicode(self.executable.name)

    @property
    def module(self):
        return self.executable.get_parent_until()

    def __repr__(self):
        return '<%s: %s index %s>' % (type(self).__name__, self.executable,
                                    self.index)
