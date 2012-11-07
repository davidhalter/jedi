""" The classes returned by the api """

import re
import os

import settings
import evaluate
import parsing
import keywords


class BaseOutput(object):
    def __init__(self, start_pos, definition):
        self.module_path = str(definition.get_parent_until().path)
        self.start_pos = start_pos
        self.definition = definition

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
    def description(self):
        raise NotImplementedError('Base Class')

    def __repr__(self):
        return "<%s %s>" % (type(self).__name__, self.description)


class Completion(object):
    """ `Completion` objects are returned from `Script.complete`. Providing
    some useful functions for IDE's. """
    def __init__(self, name, needs_dot, like_name_length, base):
        self.name = name
        self.needs_dot = needs_dot
        self.like_name_length = like_name_length
        self._completion_parent = name.parent()  # limit gc
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
        funcs = (parsing.Function, evaluate.Function)
        if settings.add_bracket_after_function \
                    and self._completion_parent.isinstance(funcs):
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
        return '' if parent is None else str(parent)

    @property
    def doc(self):
        """ Return a document string for this completion object. """
        try:
            return self.name.parent().doc
        except AttributeError:
            return self.raw_doc

    @property
    def raw_doc(self):
        """ Returns the docstring `__doc__` for any object """
        try:
            return str(self.name.parent().docstr)
        except AttributeError :
            return ''

    @property
    def type(self):
        """ Returns the type of a completion object (e.g. Function/Class) """
        if self.name.parent is None:
            return ''
        name_type = self.name.parent()
        if isinstance(self.name_type, evaluate.InstanceElement):
            name_type = name_type.var
        return type(self.name_var).__class__

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.name)


class Definition(BaseOutput):
    """ These are the objects returned by either `Script.goto` or
    `Script.get_definition`. """
    def __init__(self, definition):
        super(Definition, self).__init__(definition.start_pos, definition)
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
        elif isinstance(d, keywords.Keyword):
            d = 'keyword %s' % d.name
        else:
            d = d.get_code().replace('\n', '')
        return d

    @property
    def doc(self):
        """ Returns the docstr, behaves like `Completion.doc`. """
        try:
            return self.definition.doc
        except AttributeError:
            return self.raw_doc

    @property
    def raw_doc(self):
        """ Returns the docstring `__doc__` for any object """
        try:
            return str(self.definition.docstr)
        except AttributeError:
            return ''

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


class RelatedName(BaseOutput):
    def __init__(self, name_part, scope):
        super(RelatedName, self).__init__(name_part.start_pos, scope)
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
