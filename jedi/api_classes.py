""" The classes returned by the api """

import re
import os

import settings
import evaluate
import parsing
import keywords


class BaseOutput(object):
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

        # generate the type
        self.stripped_definition = self.definition
        if isinstance(self.definition, evaluate.InstanceElement):
            self.stripped_definition = self.definition.var
        self.type = type(self.stripped_definition).__name__

        # generate a path to the definition
        self.module_path = str(definition.get_parent_until().path)
        self.path = []
        if not isinstance(definition, keywords.Keyword):
            par = definition
            while par is not None:
                try:
                    self.path.insert(0, par.name)
                except AttributeError:
                    pass
                par = par.parent()

    @property
    def module_name(self):
        path = self.module_path
        sep = os.path.sep
        p = re.sub(r'^.*?([\w\d]+)(%s__init__)?.py$' % sep, r'\1', path)
        return p

    def in_builtin_module(self):
        return not self.module_path.endswith('.py')

    @property
    def line_nr(self):
        return self.start_pos[0]

    @property
    def column(self):
        return self.start_pos[1]

    @property
    def doc(self):
        """ Return a document string for this completion object. """
        try:
            return self.definition.doc
        except AttributeError:
            return self.raw_doc

    @property
    def raw_doc(self):
        """ Returns the raw docstring `__doc__` for any object """
        try:
            return str(self.definition.docstr)
        except AttributeError:
            return ''

    @property
    def description(self):
        raise NotImplementedError('Base Class')

    @property
    def full_name(self):
        """
        Returns the path to a certain class/function, see #61.
        """
        path = [str(p) for p in self.path]
        # TODO add further checks, the mapping should only occur on stdlib.
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


class Completion(BaseOutput):
    """ `Completion` objects are returned from `Script.complete`. Providing
    some useful functions for IDE's. """
    def __init__(self, name, needs_dot, like_name_length, base):
        super(Completion, self).__init__(name.parent(), name.start_pos)

        self.name = name
        self.needs_dot = needs_dot
        self.like_name_length = like_name_length
        self.base = base

    @property
    def complete(self):
        """ Delievers the rest of the word, e.g. completing `isinstance`
        >>> isinstan

        would return the string 'ce'. It also adds additional stuff, depending
        on your `settings.py`
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
        """ In contrary to `complete` returns the whole word, e.g.
        >>> isinstan

        would return 'isinstance'.
        """
        return str(self.name.names[-1])

    @property
    def description(self):
        """ Provides a description of the completion object
        TODO return value is just __repr__ of some objects, improve! """
        parent = self.name.parent()
        if parent is None:
            return ''
        t = self.type
        if t == 'Statement' or t == 'Import':
            desc = self.definition.get_code(False)
        else:
            desc = '.'.join(str(p) for p in self.path)

        line_nr = '' if self.in_builtin_module else '@%s' % self.line_nr
        return '%s: %s%s' % (t, desc, line_nr)

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.name)


class Definition(BaseOutput):
    """ These are the objects returned by either `Script.goto` or
    `Script.get_definition`. """
    def __init__(self, definition):
        super(Definition, self).__init__(definition, definition.start_pos)
        self._def_parent = definition.parent()  # just here to limit gc

    @property
    def description(self):
        """ A description of the Definition object, which is heavily used in
        testing. e.g. for `isinstance` it returns 'def isinstance' """
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
        elif self.is_keyword:
            d = 'keyword %s' % d.name
        else:
            d = d.get_code().replace('\n', '')
        return d

    @property
    def desc_with_module(self):
        """ In addition to the Definition, it also returns the module. Don't
        use it yet, its behaviour may change. If you really need it, talk to me
        TODO add full path. This function is should return a
        module.class.function path. """
        if self.module_path.endswith('.py') \
                    and not isinstance(self.definition, parsing.Module):
            position = '@%s' % (self.line_nr)
        else:
            # is a builtin or module
            position = ''
        return "%s:%s%s" % (self.module_name, self.description, position)


class RelatedName(BaseOutput):
    def __init__(self, name_part, scope):
        super(RelatedName, self).__init__(scope, name_part.start_pos)
        self.name_part = name_part
        self.text = str(name_part)
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
        return str(self.executable.name)

    @property
    def module(self):
        return self.executable.get_parent_until()

    def __repr__(self):
        return '<%s: %s index %s>' % (type(self).__name__, self.executable,
                                    self.index)
