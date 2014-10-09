"""
If you know what an abstract syntax tree (ast) is, you'll see that this module
is pretty much that. The classes represent syntax elements: ``Import``,
``Function``.

A very central class is ``Scope``. It is not used directly by the parser, but
inherited. It's used by ``Function``, ``Class``, ``Flow``, etc. A ``Scope`` may
have ``subscopes``, ``imports`` and ``statements``. The entire parser is based
on scopes, because they also stand for indentation.

One special thing:

``Array`` values are statements. But if you think about it, this makes sense.
``[1, 2+33]`` for example would be an Array with two ``Statement`` inside. This
is the easiest way to write a parser. The same behaviour applies to ``Param``,
which is being used in a function definition.

The easiest way to play with this module is to use :class:`parsing.Parser`.
:attr:`parsing.Parser.module` holds an instance of :class:`SubModule`:

>>> from jedi._compatibility import u
>>> from jedi.parser import Parser
>>> parser = Parser(u('import os'), 'example.py')
>>> submodule = parser.module
>>> submodule
<SubModule: example.py@1-1>

Any subclasses of :class:`Scope`, including :class:`SubModule` has
attribute :attr:`imports <Scope.imports>`.  This attribute has import
statements in this scope.  Check this out:

>>> submodule.imports
[<Import: import os @1,0>]

See also :attr:`Scope.subscopes` and :attr:`Scope.statements`.
"""
import os
import re
from inspect import cleandoc
from collections import defaultdict

from jedi._compatibility import (next, Python3Method, encoding, unicode,
                                 is_py3, u, literal_eval, use_metaclass)
from jedi import common
from jedi import debug
from jedi import cache
from jedi.parser import tokenize


SCOPE_CONTENTS = 'asserts', 'subscopes', 'imports', 'statements', 'returns'


def filter_after_position(names, position):
    """
    Removes all names after a certain position. If position is None, just
    returns the names list.
    """
    if position is None:
        return names

    names_new = []
    for n in names:
        if n.start_pos[0] is not None and n.start_pos < position:
            names_new.append(n)
    return names_new


class GetCodeState(object):
    """A helper class for passing the state of get_code in a thread-safe
    manner."""
    __slots__ = ("last_pos",)

    def __init__(self):
        self.last_pos = (0, 0)


class DocstringMixin(object):
    __slots__ = ()

    def add_docstr(self, token):
        """ Clean up a docstring """
        self._doc_token = token

    @property
    def raw_doc(self):
        """ Returns a cleaned version of the docstring token. """
        try:
            # Returns a literal cleaned version of the ``Token``.
            cleaned = cleandoc(literal_eval(self._doc_token.string))
            # Since we want the docstr output to be always unicode, just force
            # it.
            if is_py3 or isinstance(cleaned, unicode):
                return cleaned
            else:
                return unicode(cleaned, 'UTF-8', 'replace')
        except AttributeError:
            return u('')


class Base(object):
    """
    This is just here to have an isinstance check, which is also used on
    evaluate classes. But since they have sometimes a special type of
    delegation, it is important for those classes to override this method.

    I know that there is a chance to do such things with __instancecheck__, but
    since Python 2.5 doesn't support it, I decided to do it this way.
    """
    __slots__ = ()

    def isinstance(self, *cls):
        return isinstance(self, cls)

    @property
    def newline(self):
        """Returns the newline type for the current code."""
        # TODO: we need newline detection
        return "\n"

    @property
    def whitespace(self):
        """Returns the whitespace type for the current code: tab or space."""
        # TODO: we need tab detection
        return " "

    @Python3Method
    def get_parent_until(self, classes=(), reverse=False,
                         include_current=True):
        """
        Searches the parent "chain" until the object is an instance of
        classes. If classes is empty return the last parent in the chain
        (is without a parent).
        """
        if type(classes) not in (tuple, list):
            classes = (classes,)
        scope = self if include_current else self.parent
        while scope.parent is not None:
            # TODO why if classes?
            if classes and reverse != scope.isinstance(*classes):
                break
            scope = scope.parent
        return scope

    def get_parent_scope(self):
        """
        Returns the underlying scope.
        """
        scope = self.parent
        while scope.parent is not None:
            if scope.is_scope():
                break
            scope = scope.parent
        return scope

    def space(self, from_pos, to_pos):
        """Return the space between two tokens"""
        linecount = to_pos[0] - from_pos[0]
        if linecount == 0:
            return self.whitespace * (to_pos[1] - from_pos[1])
        else:
            return "%s%s" % (
                self.newline * linecount,
                self.whitespace * to_pos[1],
            )

    def is_scope(self):
        # Default is not being a scope. Just inherit from Scope.
        return False


class _Leaf(Base):
    __slots__ = ('value', 'parent', 'start_pos', 'prefix')

    def __init__(self, value, start_pos, prefix):
        self.value = value
        self.start_pos = start_pos
        self.prefix = prefix

    @property
    def end_pos(self):
        return self.start_pos[0], self.start_pos[1] + len(self.value)

    def get_code(self):
        return self.prefix + self.value

    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, repr(self.value))


class Whitespace(_Leaf):
    """Contains NEWLINE and ENDMARKER tokens."""


class Name(_Leaf):
    """
    A string. Sometimes it is important to know if the string belongs to a name
    or not.
    """
    # Unfortunately there's no way to use slots for str (non-zero __itemsize__)
    # -> http://utcc.utoronto.ca/~cks/space/blog/python/IntSlotsPython3k
    # Therefore don't subclass `str`.

    def __str__(self):
        return self.value

    def __unicode__(self):
        return self.value

    def __repr__(self):
        return "<%s: %s@%s,%s>" % (type(self).__name__, self.value,
                                   self.start_pos[0], self.start_pos[1])

    def get_definition(self):
        return self.get_parent_until((ArrayStmt, StatementElement), reverse=True)


class Literal(_Leaf):
    def eval(self):
        return literal_eval(self.value)

    def __repr__(self):
        if is_py3:
            s = self.literal
        else:
            s = self.literal.encode('ascii', 'replace')
        return "<%s: %s>" % (type(self).__name__, s)


class Operator(_Leaf):
    def __str__(self):
        return self.get_code()

    def __eq__(self, other):
        """
        Make comparisons with strings easy.
        Improves the readability of the parser.
        """
        if isinstance(other, Operator):
            return self is other
        else:
            return self.value == other

    def __ne__(self, other):
        """Python 2 compatibility."""
        return self.value != other

    def __hash__(self):
        return hash(self.value)


class Simple(Base):
    """
    The super class for Scope, Import, Name and Statement. Every object in
    the parser tree inherits from this class.
    """
    __slots__ = ('children', 'parent')

    def __init__(self, children):
        """
        Initialize :class:`Simple`.

        :type  children: :class:`SubModule`
        :param children: The module in which this Python object locates.
        """
        self.children = children
        self.parent = None

    @property
    def start_pos(self):
        return self.children[0].start_pos

    @property
    def _sub_module(self):
        return self.get_parent_until()

    @property
    def end_pos(self):
        return self.children[-1].end_pos

    def get_code(self):
        return "".join(str(c) for c in self.children)

    def __repr__(self):
        code = self.get_code().replace('\n', ' ')
        if not is_py3:
            code = code.encode(encoding, 'replace')
        return "<%s: %s@%s,%s>" % \
            (type(self).__name__, code, self.start_pos[0], self.start_pos[1])


class IsScopeMeta(type):
    def __instancecheck__(self, other):
        return other.is_scope()


class IsScope(use_metaclass(IsScopeMeta)):
    pass


def _return_empty_list():
    """
    Necessary for pickling. It needs to be reachable for pickle, cannot
    be a lambda or a closure.
    """
    return []


class Scope(Simple, DocstringMixin):
    """
    Super class for the parser tree, which represents the state of a python
    text file.
    A Scope manages and owns its subscopes, which are classes and functions, as
    well as variables and imports. It is used to access the structure of python
    files.

    :param start_pos: The position (line and column) of the scope.
    :type start_pos: tuple(int, int)
    """
    __slots__ = ('subscopes', 'imports', 'statements', '_doc_token', 'asserts',
                 'returns', 'is_generator', '_names_dict')

    def __init__(self, children):
        super(Scope, self).__init__(children)
        self.subscopes = []
        self.imports = []
        self.statements = []
        self._doc_token = None
        self.asserts = []
        # Needed here for fast_parser, because the fast_parser splits and
        # returns will be in "normal" modules.
        self.returns = []
        self._names_dict = defaultdict(_return_empty_list)
        self.is_generator = False

    def is_scope(self):
        return True

    def add_name_calls(self, name, calls):
        """Add a name to the names_dict."""
        self._names_dict[name] += calls

    def get_names_dict(self):
        return self._names_dict

    def add_scope(self, sub, decorators):
        sub.parent = self.use_as_parent
        sub.decorators = decorators
        for d in decorators:
            # the parent is the same, because the decorator has not the scope
            # of the function
            d.parent = self.use_as_parent
        self.subscopes.append(sub)
        return sub

    def add_statement(self, stmt):
        """
        Used to add a Statement or a Scope.
        A statement would be a normal command (Statement) or a Scope (Flow).
        """
        stmt.parent = self.use_as_parent
        self.statements.append(stmt)
        return stmt

    def add_import(self, imp):
        self.imports.append(imp)
        imp.parent = self.use_as_parent

    def get_imports(self):
        """ Gets also the imports within flow statements """
        i = [] + self.imports
        for s in self.statements:
            if isinstance(s, Scope):
                i += s.get_imports()
        return i

    def get_code2(self, state=GetCodeState()):
        string = []
        return "".join(string)

    def get_code(self, first_indent=False, indention='    '):
        """
        :return: Returns the code of the current scope.
        :rtype: str
        """
        string = ""
        if self._doc_token is not None:
            string += '"""' + self.raw_doc + '"""\n'

        objs = self.subscopes + self.imports + self.statements + self.returns
        for obj in sorted(objs, key=lambda x: x.start_pos):
            if isinstance(obj, Scope):
                string += obj.get_code(first_indent=True, indention=indention)
            else:
                if obj in self.returns and not isinstance(self, Lambda):
                    string += 'yield ' if self.is_generator else 'return '
                string += obj.get_code()

        if first_indent:
            string = common.indent_block(string, indention=indention)
        return string

    @Python3Method
    def get_defined_names(self):
        """
        Get all defined names in this scope.

        >>> from jedi._compatibility import u
        >>> from jedi.parser import Parser
        >>> parser = Parser(u('''
        ... a = x
        ... b = y
        ... b.c = z
        ... '''))
        >>> parser.module.get_defined_names()
        [<Name: a@2,0>, <Name: b@3,0>, <Name: b.c@4,0>]
        """
        n = []
        for stmt in self.statements:
            try:
                n += stmt.get_defined_names(True)
            except TypeError:
                n += stmt.get_defined_names()

        # function and class names
        n += [s.name for s in self.subscopes]

        for i in self.imports:
            if not i.star:
                n += i.get_defined_names()
        return n

    @Python3Method
    def get_statement_for_position(self, pos, include_imports=False):
        checks = self.statements + self.asserts
        if include_imports:
            checks += self.imports
        if self.isinstance(Function):
            checks += self.params + self.decorators
            checks += [r for r in self.returns if r is not None]
        if self.isinstance(Flow):
            checks += self.inputs
        if self.isinstance(ForFlow) and self.set_stmt is not None:
            checks.append(self.set_stmt)

        for s in checks:
            if isinstance(s, Flow):
                p = s.get_statement_for_position(pos, include_imports)
                while s.next and not p:
                    s = s.next
                    p = s.get_statement_for_position(pos, include_imports)
                if p:
                    return p
            elif s.start_pos <= pos <= s.end_pos:
                return s

        for s in self.subscopes:
            if s.start_pos <= pos <= s.end_pos:
                p = s.get_statement_for_position(pos, include_imports)
                if p:
                    return p

    def __repr__(self):
        try:
            name = self.path
        except AttributeError:
            try:
                name = self.name
            except AttributeError:
                name = self.command

        return "<%s: %s@%s-%s>" % (type(self).__name__, name,
                                   self.start_pos[0], self.end_pos[0])

    def walk(self):
        yield self
        for s in self.subscopes:
            for scope in s.walk():
                yield scope

        for r in self.statements:
            while isinstance(r, Flow):
                for scope in r.walk():
                    yield scope
                r = r.next


class Module(Base):
    """
    For isinstance checks. fast_parser.Module also inherits from this.
    """
    def is_scope(self):
        return True


class SubModule(Scope, Module):
    """
    The top scope, which is always a module.
    Depending on the underlying parser this may be a full module or just a part
    of a module.
    """
    __slots__ = ('path', 'global_vars', 'used_names', 'temp_used_names',
                 'line_offset', 'use_as_parent')

    def __init__(self, children):
        """
        Initialize :class:`SubModule`.

        :type path: str
        :arg  path: File path to this module.

        .. todo:: Document `top_module`.
        """
        super(SubModule, self).__init__(children)
        self.path = None  # Set later.
        self.global_vars = []
        self.used_names = {}
        self.temp_used_names = []
        # this may be changed depending on fast_parser
        self.line_offset = 0

        if 0:
            self.use_as_parent = top_module or self

    def add_global(self, name):
        """
        Global means in these context a function (subscope) which has a global
        statement.
        This is only relevant for the top scope.

        :param name: The name of the global.
        :type name: Name
        """
        # set no parent here, because globals are not defined in this scope.
        self.global_vars.append(name)

    def get_defined_names(self):
        n = super(SubModule, self).get_defined_names()
        n += self.global_vars
        return n

    @property
    @cache.underscore_memoization
    def name(self):
        """ This is used for the goto functions. """
        if self.path is None:
            string = ''  # no path -> empty name
        else:
            sep = (re.escape(os.path.sep),) * 2
            r = re.search(r'([^%s]*?)(%s__init__)?(\.py|\.so)?$' % sep, self.path)
            # Remove PEP 3149 names
            string = re.sub('\.[a-z]+-\d{2}[mud]{0,3}$', '', r.group(1))
        # Positions are not real, but a module starts at (1, 0)
        p = (1, 0)
        return Name(self, string, self.use_as_parent, p)

    @property
    def has_explicit_absolute_import(self):
        """
        Checks if imports in this module are explicitly absolute, i.e. there
        is a ``__future__`` import.
        """
        for imp in self.imports:
            if not imp.from_names or not imp.namespace_names:
                continue

            namespace, feature = imp.from_names[0], imp.namespace_names[0]
            if unicode(namespace) == "__future__" and unicode(feature) == "absolute_import":
                return True

        return False


class Class(Scope):
    """
    Used to store the parsed contents of a python class.

    :param name: The Class name.
    :type name: str
    :param supers: The super classes of a Class.
    :type supers: list
    :param start_pos: The start position (line, column) of the class.
    :type start_pos: tuple(int, int)
    """
    __slots__ = ('name', 'supers', 'decorators')

    def __init__(self, module, name, supers, start_pos):
        super(Class, self).__init__(module, start_pos)
        self.name = name
        name.parent = self.use_as_parent
        self.supers = supers
        for s in self.supers:
            s.parent = self.use_as_parent
        self.decorators = []

    def get_code(self, first_indent=False, indention='    '):
        string = "\n".join('@' + stmt.get_code() for stmt in self.decorators)
        string += 'class %s' % (self.name)
        if len(self.supers) > 0:
            sup = ', '.join(stmt.get_code(False) for stmt in self.supers)
            string += '(%s)' % sup
        string += ':\n'
        string += super(Class, self).get_code(True, indention)
        return string

    @property
    def doc(self):
        """
        Return a document string including call signature of __init__.
        """
        docstr = ""
        if self._doc_token is not None:
            docstr = self.raw_doc
        for sub in self.subscopes:
            if unicode(sub.name) == '__init__':
                return '%s\n\n%s' % (
                    sub.get_call_signature(funcname=self.name), docstr)
        return docstr

    def scope_names_generator(self, position=None):
        yield self, filter_after_position(self.get_defined_names(), position)


class Function(Scope):
    """
    Used to store the parsed contents of a python function.

    :param name: The Function name.
    :type name: str
    :param params: The parameters (Statement) of a Function.
    :type params: list
    :param start_pos: The start position (line, column) the Function.
    :type start_pos: tuple(int, int)
    """
    __slots__ = ('decorators', 'listeners')

    def __init__(self, children):
        super(Function, self).__init__(children)
        self.decorators = []
        self.listeners = set()  # not used here, but in evaluation.

    @property
    def name(self):
        return self.children[1]  # First token after `def`

    def params(self):
        return self.children[3].children  # After def foo(

    def annotation(self):
        try:
            return self.children[6]  # 6th element: def foo(...) -> bar
        except IndexError:
            return None

    def get_defined_names(self):
        n = super(Function, self).get_defined_names()
        for p in self.params:
            try:
                n.append(p.get_name())
            except IndexError:
                debug.warning("multiple names in param %s", n)
        return n

    def scope_names_generator(self, position=None):
        yield self, filter_after_position(self.get_defined_names(), position)

    def get_call_signature(self, width=72, funcname=None):
        """
        Generate call signature of this function.

        :param width: Fold lines if a line is longer than this value.
        :type width: int
        :arg funcname: Override function name when given.
        :type funcname: str

        :rtype: str
        """
        l = unicode(funcname or self.name) + '('
        lines = []
        for (i, p) in enumerate(self.params):
            code = p.get_code(False)
            if i != len(self.params) - 1:
                code += ', '
            if len(l + code) > width:
                lines.append(l[:-1] if l[-1] == ' ' else l)
                l = code
            else:
                l += code
        if l:
            lines.append(l)
        lines[-1] += ')'
        return '\n'.join(lines)

    @property
    def doc(self):
        """ Return a document string including call signature. """
        docstr = ""
        if self._doc_token is not None:
            docstr = self.raw_doc
        return '%s\n\n%s' % (self.get_call_signature(), docstr)


class Lambda(Function):
    def __init__(self, module, params, start_pos, parent):
        super(Lambda, self).__init__(module, None, params, start_pos, None)
        self.parent = parent

    def get_code(self, first_indent=False, indention='    '):
        params = ','.join([stmt.get_code() for stmt in self.params])
        string = "lambda %s: " % params
        return string + super(Function, self).get_code(indention=indention)

    def __repr__(self):
        return "<%s @%s (%s-%s)>" % (type(self).__name__, self.start_pos[0],
                                     self.start_pos[1], self.end_pos[1])


class Flow(Scope):
    """
    Used to describe programming structure - flow statements,
    which indent code, but are not classes or functions:

    - for
    - while
    - if
    - try
    - with

    Therefore statements like else, except and finally are also here,
    they are now saved in the root flow elements, but in the next variable.

    :param command: The flow command, if, while, else, etc.
    :type command: str
    :param inputs: The initializations of a flow -> while 'statement'.
    :type inputs: list(Statement)
    :param start_pos: Position (line, column) of the Flow statement.
    :type start_pos: tuple(int, int)
    """
    __slots__ = ('next', 'previous', 'command', '_parent', 'inputs', 'set_vars')

    def __init__(self, module, command, inputs, start_pos):
        self.next = None
        self.previous = None
        self.command = command
        super(Flow, self).__init__(module, start_pos)
        self._parent = None
        # These have to be statements, because of with, which takes multiple.
        self.inputs = inputs
        for s in inputs:
            s.parent = self.use_as_parent
        self.set_vars = []

    def add_name_calls(self, name, calls):
        """Add a name to the names_dict."""
        parent = self.parent
        if isinstance(parent, Module):
            # TODO this also looks like code smell. Look for opportunities to
            # remove.
            parent = self._sub_module
        parent.add_name_calls(name, calls)

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, value):
        self._parent = value
        try:
            self.next.parent = value
        except AttributeError:
            return

    def get_code(self, first_indent=False, indention='    '):
        stmts = []
        for s in self.inputs:
            stmts.append(s.get_code(new_line=False))
        stmt = ', '.join(stmts)
        string = "%s %s:\n" % (self.command, stmt)
        string += super(Flow, self).get_code(True, indention)
        if self.next:
            string += self.next.get_code()
        return string

    def get_defined_names(self, is_internal_call=False):
        """
        Get the names for the flow. This includes also a call to the super
        class.

        :param is_internal_call: defines an option for internal files to crawl
            through this class. Normally it will just call its superiors, to
            generate the output.
        """
        if is_internal_call:
            n = list(self.set_vars)
            for s in self.inputs:
                n += s.get_defined_names()
            if self.next:
                n += self.next.get_defined_names(is_internal_call)
            n += super(Flow, self).get_defined_names()
            return n
        else:
            return self.get_parent_until((Class, Function)).get_defined_names()

    def get_imports(self):
        i = super(Flow, self).get_imports()
        if self.next:
            i += self.next.get_imports()
        return i

    def set_next(self, next):
        """Set the next element in the flow, those are else, except, etc."""
        if self.next:
            return self.next.set_next(next)
        else:
            self.next = next
            self.next.parent = self.parent
            self.next.previous = self
            return next

    def scope_names_generator(self, position=None):
        # For `with` and `for`.
        yield self, filter_after_position(self.get_defined_names(), position)


class ForFlow(Flow):
    """
    Used for the for loop, because there are two statement parts.
    """
    def __init__(self, module, inputs, start_pos, set_stmt):
        super(ForFlow, self).__init__(module, 'for', inputs, start_pos)

        self.set_stmt = set_stmt

        if set_stmt is not None:
            set_stmt.parent = self.use_as_parent
            self.set_vars = set_stmt.get_defined_names()

            for s in self.set_vars:
                s.parent.parent = self.use_as_parent
                s.parent = self.use_as_parent

    def get_code(self, first_indent=False, indention=" " * 4):
        vars = ",".join(x.get_code() for x in self.set_vars)
        stmts = []
        for s in self.inputs:
            stmts.append(s.get_code(new_line=False))
        stmt = ', '.join(stmts)
        s = "for %s in %s:\n" % (vars, stmt)
        return s + super(Flow, self).get_code(True, indention)


class Import(Simple):
    """
    Stores the imports of any Scopes.

    :param start_pos: Position (line, column) of the Import.
    :type start_pos: tuple(int, int)
    :param namespace_names: The import, can be empty if a star is given
    :type namespace_names: list of Name
    :param alias: The alias of a namespace(valid in the current namespace).
    :type alias: list of Name
    :param from_names: Like the namespace, can be equally used.
    :type from_names: list of Name
    :param star: If a star is used -> from time import *.
    :type star: bool
    :param defunct: An Import is valid or not.
    :type defunct: bool
    """
    def __init__(self, module, start_pos, end_pos, namespace_names, alias=None,
                 from_names=(), star=False, relative_count=0, defunct=False):
        super(Import, self).__init__(module, start_pos, end_pos)

        self.namespace_names = namespace_names
        self.alias = alias
        if self.alias:
            alias.parent = self
        self.from_names = from_names
        for n in namespace_names + list(from_names):
            n.parent = self.use_as_parent

        self.star = star
        self.relative_count = relative_count
        self.defunct = defunct

    def get_code(self, new_line=True):
        # in case one of the names is None
        alias = self.alias or ''

        ns_str = '.'.join(unicode(n) for n in self.namespace_names)
        if self.alias:
            ns_str = "%s as %s" % (ns_str, alias)

        nl = '\n' if new_line else ''
        if self.from_names or self.relative_count:
            if self.star:
                ns_str = '*'
            dots = '.' * self.relative_count
            from_txt = '.'.join(unicode(n) for n in self.from_names)
            return "from %s%s import %s%s" % (dots, from_txt, ns_str, nl)
        else:
            return "import %s%s" % (ns_str, nl)

    def get_defined_names(self):
        if self.defunct:
            return []
        if self.star:
            return [self]
        if self.alias:
            return [self.alias]
        if len(self.namespace_names) > 1:
            return [self.namespace_names[0]]
        else:
            return self.namespace_names

    def get_all_import_names(self):
        n = []
        if self.from_names:
            n += self.from_names
        if self.namespace_names:
            n += self.namespace_names
        if self.alias is not None:
            n.append(self.alias)
        return n

    def is_nested(self):
        """
        This checks for the special case of nested imports, without aliases and
        from statement::

            import foo.bar
        """
        return not self.alias and not self.from_names \
            and len(self.namespace_names) > 1


class KeywordStatement(Base):
    """
    For the following statements: `assert`, `del`, `global`, `nonlocal`,
    `raise`, `return`, `yield`, `pass`, `continue`, `break`, `return`, `yield`.
    """
    __slots__ = ('name', 'start_pos', 'stmt', 'parent')

    def __init__(self, name, start_pos, parent, stmt=None):
        self.name = name
        self.start_pos = start_pos
        self.stmt = stmt
        self.parent = parent

        if stmt is not None:
            stmt.parent = self

    def __repr__(self):
        return "<%s(%s): %s>" % (type(self).__name__, self.name, self.stmt)

    def get_code(self):
        if self.stmt is None:
            return "%s\n" % self.name
        else:
            return '%s %s\n' % (self.name, self.stmt)

    def get_defined_names(self):
        return []

    @property
    def end_pos(self):
        try:
            return self.stmt.end_pos
        except AttributeError:
            return self.start_pos[0], self.start_pos[1] + len(self.name)


class Statement(Simple, DocstringMixin):
    """
    This is the class for all the possible statements. Which means, this class
    stores pretty much all the Python code, except functions, classes, imports,
    and flow functions like if, for, etc.

    :type  token_list: list
    :param token_list:
        List of tokens or names.  Each element is either an instance
        of :class:`Name` or a tuple of token type value (e.g.,
        :data:`tokenize.NUMBER`), token string (e.g., ``'='``), and
        start position (e.g., ``(1, 0)``).
    :type   start_pos: 2-tuple of int
    :param  start_pos: Position (line, column) of the Statement.
    """
    __slots__ = ('_token_list', '_set_vars', 'as_names', '_expression_list',
                 '_assignment_details', '_names_are_set_vars', '_doc_token')

    def __init__(self, module, token_list, start_pos, end_pos, parent=None,
                 as_names=(), names_are_set_vars=False, set_name_parents=True):
        super(Statement, self).__init__(module, start_pos, end_pos, parent)
        self._token_list = token_list
        self._names_are_set_vars = names_are_set_vars
        if set_name_parents:
            for n in as_names:
                n.parent = self.use_as_parent
        self._doc_token = None
        self._set_vars = None
        self.as_names = list(as_names)

        # cache
        self._assignment_details = []
        # For now just generate the expression list, even if its not needed.
        # This will help to adapt a better new AST.
        self.expression_list()

    @property
    def end_pos(self):
        return self._token_list[-1].end_pos

    def get_code(self, new_line=True):
        def assemble(command_list, assignment=None):
            pieces = [c.get_code() if isinstance(c, Simple) else c.string
                      if isinstance(c, tokenize.Token) else unicode(c)
                      for c in command_list]
            if assignment is None:
                return ''.join(pieces)
            return '%s %s ' % (''.join(pieces), assignment)

        code = ''.join(assemble(*a) for a in self.assignment_details)
        code += assemble(self.expression_list())
        if self._doc_token:
            code += '\n"""%s"""' % self.raw_doc

        if new_line:
            return code + '\n'
        else:
            return code

    def get_defined_names(self):
        """Get the names for the statement."""
        if self._set_vars is None:

            def search_calls(calls):
                for call in calls:
                    if isinstance(call, Array) and call.type != Array.DICT:
                        for stmt in call:
                            search_calls(stmt.expression_list())
                    elif isinstance(call, Call):
                        # Check if there's an execution in it, if so this is
                        # not a set_var.
                        if not call.next:
                            self._set_vars.append(call.name)
                        continue

            self._set_vars = []
            for calls, operation in self.assignment_details:
                search_calls(calls)

            if not self.assignment_details and self._names_are_set_vars:
                # In the case of Param, it's also a defining name without ``=``
                search_calls(self.expression_list())
        return self._set_vars + self.as_names

    def get_names_dict(self):
        """The future of name resolution. Returns a dict(str -> Call)."""
        dct = defaultdict(lambda: [])

        def search_calls(calls):
            for call in calls:
                if isinstance(call, Array) and call.type != Array.DICT:
                    for stmt in call:
                        search_calls(stmt.expression_list())
                elif isinstance(call, Call):
                    c = call
                    # Check if there's an execution in it, if so this is
                    # not a set_var.
                    while True:
                        if c.next is None or isinstance(c.next, Array):
                            break
                        c = c.next
                    dct[unicode(c.name)].append(call)

        for calls, operation in self.assignment_details:
            search_calls(calls)

        if not self.assignment_details and self._names_are_set_vars:
            # In the case of Param, it's also a defining name without ``=``
            search_calls(self.expression_list())

        for as_name in self.as_names:
            dct[unicode(as_name)].append(Call(self._sub_module, as_name,
                                         as_name.start_pos, as_name.end_pos, self))
        return dct

    def is_global(self):
        p = self.parent
        return isinstance(p, KeywordStatement) and p.name == 'global'

    @property
    def assignment_details(self):
        """
        Returns an array of tuples of the elements before the assignment.

        For example the following code::

            x = (y, z) = 2, ''

        would result in ``[(Name(x), '='), (Array([Name(y), Name(z)]), '=')]``.
        """
        # parse statement which creates the assignment details.
        self.expression_list()
        return self._assignment_details

    @cache.underscore_memoization
    def expression_list(self):
        """
        Parse a statement.
        """
        return self.children

    def set_expression_list(self, lst):
        """It's necessary for some "hacks" to change the expression_list."""
        self._expression_list = lst


class ExprStmt(Statement):
    """
    This class exists temporarily, to be able to distinguish real statements
    (``small_stmt`` in Python grammar) from the so called ``test`` parts, that
    may be used to defined part of an array, but are never a whole statement.

    The reason for this class is purely historical. It was easier to just use
    Statement nested, than to create a new class for Test (plus Jedi's fault
    tolerant parser just makes things very complicated).
    """


class ArrayStmt(Statement):
    """
    This class exists temporarily. Like ``ExprStatement``, this exists to
    distinguish between real statements and stuff that is defined in those
    statements.
    """


class Param(ExprStmt):
    """
    The class which shows definitions of params of classes and functions.
    But this is not to define function calls.
    """
    __slots__ = ('position_nr', 'is_generated', 'annotation_stmt',
                 'parent_function')

    def __init__(self, *args, **kwargs):
        kwargs.pop('names_are_set_vars', None)
        super(Param, self).__init__(*args, names_are_set_vars=True, **kwargs)

        # this is defined by the parser later on, not at the initialization
        # it is the position in the call (first argument, second...)
        self.position_nr = None
        self.is_generated = False
        self.annotation_stmt = None
        self.parent_function = None

    def add_annotation(self, annotation_stmt):
        annotation_stmt.parent = self.use_as_parent
        self.annotation_stmt = annotation_stmt

    def get_name(self):
        """ get the name of the param """
        n = self.get_defined_names()
        if len(n) > 1:
            debug.warning("Multiple param names (%s).", n)
        return n[0]

    @property
    def stars(self):
        exp = self.expression_list()
        if exp and isinstance(exp[0], Operator):
            return exp[0].string.count('*')
        return 0


class StatementElement(Simple):
    __slots__ = ('next', 'previous')

    def __init__(self, module, start_pos, end_pos, parent):
        super(StatementElement, self).__init__(module, start_pos, end_pos, parent)
        self.next = None
        self.previous = None

    def set_next(self, call):
        """ Adds another part of the statement"""
        call.parent = self.parent
        if self.next is not None:
            self.next.set_next(call)
        else:
            self.next = call
            call.previous = self

    def next_is_execution(self):
        return Array.is_type(self.next, Array.TUPLE, Array.NOARRAY)

    def generate_call_path(self):
        """ Helps to get the order in which statements are executed. """
        try:
            yield self.name
        except AttributeError:
            yield self
        if self.next is not None:
            for y in self.next.generate_call_path():
                yield y

    def get_code(self):
        if self.next is not None:
            s = '.' if not isinstance(self.next, Array) else ''
            return s + self.next.get_code()
        return ''


class Call(StatementElement):
    __slots__ = ('name',)

    def __init__(self, module, name, start_pos, end_pos, parent=None):
        super(Call, self).__init__(module, start_pos, end_pos, parent)
        name.parent = self
        self.name = name

    def get_code(self):
        return self.name.get_code() + super(Call, self).get_code()

    def names(self):
        """
        Generate an array of string names. If a call is not just names,
        raise an error.
        """
        def check(call):
            while call is not None:
                if not isinstance(call, Call):  # Could be an Array.
                    break
                yield unicode(call.name)
                call = call.next

        return list(check(self))


    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, self.name)


class Array(StatementElement):
    """
    Describes the different python types for an array, but also empty
    statements. In the Python syntax definitions this type is named 'atom'.
    http://docs.python.org/py3k/reference/grammar.html
    Array saves sub-arrays as well as normal operators and calls to methods.

    :param array_type: The type of an array, which can be one of the constants
        below.
    :type array_type: int
    """
    __slots__ = ('type', 'end_pos', 'values', 'keys')
    NOARRAY = None  # just brackets, like `1 * (3 + 2)`
    TUPLE = 'tuple'
    LIST = 'list'
    DICT = 'dict'
    SET = 'set'

    def __init__(self, module, start_pos, arr_type=NOARRAY, parent=None):
        super(Array, self).__init__(module, start_pos, (None, None), parent)
        self.end_pos = None, None
        self.type = arr_type
        self.values = []
        self.keys = []

    def add_statement(self, statement, is_key=False):
        """Just add a new statement"""
        statement.parent = self
        if is_key:
            self.type = self.DICT
            self.keys.append(statement)
        else:
            self.values.append(statement)

    @staticmethod
    def is_type(instance, *types):
        """
        This is not only used for calls on the actual object, but for
        ducktyping, to invoke this function with anything as `self`.
        """
        try:
            if instance.type in types:
                return True
        except AttributeError:
            pass
        return False

    def __len__(self):
        return len(self.values)

    def __getitem__(self, key):
        if self.type == self.DICT:
            raise TypeError('no dicts allowed')
        return self.values[key]

    def __iter__(self):
        if self.type == self.DICT:
            raise TypeError('no dicts allowed')
        return iter(self.values)

    def items(self):
        if self.type != self.DICT:
            raise TypeError('only dicts allowed')
        return zip(self.keys, self.values)

    def get_code(self):
        map = {
            self.NOARRAY: '(%s)',
            self.TUPLE: '(%s)',
            self.LIST: '[%s]',
            self.DICT: '{%s}',
            self.SET: '{%s}'
        }
        inner = []
        for i, stmt in enumerate(self.values):
            s = ''
            with common.ignored(IndexError):
                key = self.keys[i]
                s += key.get_code(new_line=False) + ': '
            s += stmt.get_code(new_line=False)
            inner.append(s)
        add = ',' if self.type == self.TUPLE and len(self) == 1 else ''
        s = map[self.type] % (', '.join(inner) + add)
        return s + super(Array, self).get_code()

    def __repr__(self):
        if self.type == self.NOARRAY:
            typ = 'noarray'
        else:
            typ = self.type
        return "<%s: %s%s>" % (type(self).__name__, typ, self.values)


class ListComprehension(ForFlow):
    """ Helper class for list comprehensions """
    def __init__(self, module, stmt, middle, input, parent):
        self.input = input
        nested_lc = input.expression_list()[0]
        if isinstance(nested_lc, ListComprehension):
            # is nested LC
            input = nested_lc.stmt
            nested_lc.parent = self

        super(ListComprehension, self).__init__(module, [input],
                                                stmt.start_pos, middle)
        self.parent = parent
        self.stmt = stmt
        self.middle = middle
        for s in middle, input:
            s.parent = self
        # The stmt always refers to the most inner list comprehension.
        stmt.parent = self._get_most_inner_lc()

    def _get_most_inner_lc(self):
        nested_lc = self.input.expression_list()[0]
        if isinstance(nested_lc, ListComprehension):
            return nested_lc._get_most_inner_lc()
        return self

    @property
    def end_pos(self):
        return self.stmt.end_pos

    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, self.get_code())

    def get_code(self):
        statements = self.stmt, self.middle, self.input
        code = [s.get_code().replace('\n', '') for s in statements]
        return "%s for %s in %s" % tuple(code)
