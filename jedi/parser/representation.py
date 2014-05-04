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

from jedi._compatibility import (next, Python3Method, encoding, unicode,
                                 is_py3, u, literal_eval)
from jedi import common
from jedi import debug
from jedi import cache
from jedi.parser import tokenize


SCOPE_CONTENTS = 'asserts', 'subscopes', 'imports', 'statements', 'returns'


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
            return unicode(cleandoc(literal_eval(self._doc_token.string)))
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
        #TODO: we need newline detection
        return "\n"

    @property
    def whitespace(self):
        """Returns the whitespace type for the current code: tab or space."""
        #TODO: we need tab detection
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
            if classes and reverse != scope.isinstance(*classes):
                break
            scope = scope.parent
        return scope

    def is_callable(self):
        """
        By default parser objects are not callable, we make them callable by
        the ``evaluate.representation`` objects.
        """
        return False

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


class Simple(Base):
    """
    The super class for Scope, Import, Name and Statement. Every object in
    the parser tree inherits from this class.
    """
    __slots__ = ('parent', '_sub_module', '_start_pos', 'use_as_parent',
                 '_end_pos')

    def __init__(self, module, start_pos, end_pos=(None, None)):
        """
        Initialize :class:`Simple`.

        :type      module: :class:`SubModule`
        :param     module: The module in which this Python object locates.
        :type   start_pos: 2-tuple of int
        :param  start_pos: Position (line, column) of the Statement.
        :type     end_pos: 2-tuple of int
        :param    end_pos: Same as `start_pos`.
        """
        self._sub_module = module
        self._start_pos = start_pos
        self._end_pos = end_pos

        self.parent = None
        # use this attribute if parent should be something else than self.
        self.use_as_parent = self

    @property
    def start_pos(self):
        return self._sub_module.line_offset + self._start_pos[0], \
            self._start_pos[1]

    @start_pos.setter
    def start_pos(self, value):
        self._start_pos = value

    @property
    def end_pos(self):
        if None in self._end_pos:
            return self._end_pos
        return self._sub_module.line_offset + self._end_pos[0], \
            self._end_pos[1]

    @end_pos.setter
    def end_pos(self, value):
        self._end_pos = value

    def __repr__(self):
        code = self.get_code().replace('\n', ' ')
        if not is_py3:
            code = code.encode(encoding, 'replace')
        return "<%s: %s@%s,%s>" % \
            (type(self).__name__, code, self.start_pos[0], self.start_pos[1])


class IsScope(Base):
    __slots__ = ()


class Scope(Simple, IsScope, DocstringMixin):
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
                 'returns', 'is_generator')

    def __init__(self, module, start_pos):
        super(Scope, self).__init__(module, start_pos)
        self.subscopes = []
        self.imports = []
        self.statements = []
        self._doc_token = None
        self.asserts = []
        # Needed here for fast_parser, because the fast_parser splits and
        # returns will be in "normal" modules.
        self.returns = []
        self.is_generator = False

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


class Module(IsScope):
    """
    For isinstance checks. fast_parser.Module also inherits from this.
    """


class SubModule(Scope, Module):
    """
    The top scope, which is always a module.
    Depending on the underlying parser this may be a full module or just a part
    of a module.
    """
    __slots__ = ('path', 'global_vars', 'used_names', 'temp_used_names',
                 'line_offset', 'use_as_parent')

    def __init__(self, path, start_pos=(1, 0), top_module=None):
        """
        Initialize :class:`SubModule`.

        :type path: str
        :arg  path: File path to this module.

        .. todo:: Document `top_module`.
        """
        super(SubModule, self).__init__(self, start_pos)
        self.path = path
        self.global_vars = []
        self.used_names = {}
        self.temp_used_names = []
        # this may be changed depending on fast_parser
        self.line_offset = 0

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
            # remove PEP 3149 names
            string = re.sub('\.[a-z]+-\d{2}[mud]{0,3}$', '', r.group(1))
        # positions are not real therefore choose (0, 0)
        names = [(string, (0, 0))]
        return Name(self, names, (0, 0), (0, 0), self.use_as_parent)

    @property
    def has_explicit_absolute_import(self):
        """
        Checks if imports in this module are explicitly absolute, i.e. there
        is a ``__future__`` import.
        """
        for imp in self.imports:
            if imp.from_ns is None or imp.namespace is None:
                continue

            namespace, feature = imp.from_ns.names[0], imp.namespace.names[0]
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
            if unicode(sub.name.names[-1]) == '__init__':
                return '%s\n\n%s' % (
                    sub.get_call_signature(funcname=self.name.names[-1]), docstr)
        return docstr


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
    __slots__ = ('name', 'params', 'decorators', 'listeners', 'annotation')

    def __init__(self, module, name, params, start_pos, annotation):
        super(Function, self).__init__(module, start_pos)
        self.name = name
        if name is not None:
            name.parent = self.use_as_parent
        self.params = params
        for p in params:
            p.parent = self.use_as_parent
            p.parent_function = self.use_as_parent
        self.decorators = []
        self.listeners = set()  # not used here, but in evaluation.

        if annotation is not None:
            annotation.parent = self.use_as_parent
        self.annotation = annotation

    def get_code(self, first_indent=False, indention='    '):
        string = "\n".join('@' + stmt.get_code() for stmt in self.decorators)
        params = ', '.join([stmt.get_code(False) for stmt in self.params])
        string += "def %s(%s):\n" % (self.name, params)
        string += super(Function, self).get_code(True, indention)
        return string

    def get_defined_names(self):
        n = super(Function, self).get_defined_names()
        for p in self.params:
            try:
                n.append(p.get_name())
            except IndexError:
                debug.warning("multiple names in param %s", n)
        return n

    def get_call_signature(self, width=72, funcname=None):
        """
        Generate call signature of this function.

        :param width: Fold lines if a line is longer than this value.
        :type width: int
        :arg funcname: Override function name when given.
        :type funcname: str

        :rtype: str
        """
        l = unicode(funcname or self.name.names[-1]) + '('
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
    __slots__ = ('next', 'command', '_parent', 'inputs', 'set_vars')

    def __init__(self, module, command, inputs, start_pos):
        self.next = None
        self.command = command
        super(Flow, self).__init__(module, start_pos)
        self._parent = None
        # These have to be statements, because of with, which takes multiple.
        self.inputs = inputs
        for s in inputs:
            s.parent = self.use_as_parent
        self.set_vars = []

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
            return next


class ForFlow(Flow):
    """
    Used for the for loop, because there are two statement parts.
    """
    def __init__(self, module, inputs, start_pos, set_stmt, is_list_comp=False):
        super(ForFlow, self).__init__(module, 'for', inputs, start_pos)

        self.set_stmt = set_stmt
        self.is_list_comp = is_list_comp

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
    :param namespace: The import, can be empty if a star is given
    :type namespace: Name
    :param alias: The alias of a namespace(valid in the current namespace).
    :type alias: Name
    :param from_ns: Like the namespace, can be equally used.
    :type from_ns: Name
    :param star: If a star is used -> from time import *.
    :type star: bool
    :param defunct: An Import is valid or not.
    :type defunct: bool
    """
    def __init__(self, module, start_pos, end_pos, namespace, alias=None,
                 from_ns=None, star=False, relative_count=0, defunct=False):
        super(Import, self).__init__(module, start_pos, end_pos)

        self.namespace = namespace
        self.alias = alias
        self.from_ns = from_ns
        for n in namespace, alias, from_ns:
            if n:
                n.parent = self.use_as_parent

        self.star = star
        self.relative_count = relative_count
        self.defunct = defunct

    def get_code(self, new_line=True):
        # in case one of the names is None
        alias = self.alias or ''
        namespace = self.namespace or ''
        from_ns = self.from_ns or ''

        if self.alias:
            ns_str = "%s as %s" % (namespace, alias)
        else:
            ns_str = unicode(namespace)

        nl = '\n' if new_line else ''
        if self.from_ns or self.relative_count:
            if self.star:
                ns_str = '*'
            dots = '.' * self.relative_count
            return "from %s%s import %s%s" % (dots, from_ns, ns_str, nl)
        else:
            return "import %s%s" % (ns_str, nl)

    def get_defined_names(self):
        if self.defunct:
            return []
        if self.star:
            return [self]
        if self.alias:
            return [self.alias]
        if len(self.namespace) > 1:
            o = self.namespace
            n = Name(self._sub_module, [(unicode(o.names[0]), o.start_pos)],
                     o.start_pos, o.end_pos, parent=o.parent)
            return [n]
        else:
            return [self.namespace]

    def get_all_import_names(self):
        n = []
        if self.from_ns:
            n.append(self.from_ns)
        if self.namespace:
            n.append(self.namespace)
        if self.alias:
            n.append(self.alias)
        return n


class KeywordStatement(Base):
    """
    For the following statements: `assert`, `del`, `global`, `nonlocal`,
    `raise`, `return`, `yield`, `pass`, `continue`, `break`, `return`, `yield`.
    """
    __slots__ = ('name', 'start_pos', '_stmt', 'parent')

    def __init__(self, name, start_pos, parent, stmt=None):
        self.name = name
        self.start_pos = start_pos
        self._stmt = stmt
        self.parent = parent

        if stmt is not None:
            stmt.parent = self

    def get_code(self):
        if self._stmt is None:
            return "%s\n" % self.name
        else:
            return '%s %s\n' % (self.name, self._stmt)

    def get_defined_names(self):
        return []

    @property
    def end_pos(self):
        try:
            return self._stmt.end_pos
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
        super(Statement, self).__init__(module, start_pos, end_pos)
        self._token_list = token_list
        self._names_are_set_vars = names_are_set_vars
        if set_name_parents:
            for t in token_list:
                if isinstance(t, Name):
                    t.parent = self.use_as_parent
            for n in as_names:
                n.parent = self.use_as_parent
        self.parent = parent
        self._doc_token = None
        self._set_vars = None
        self.as_names = list(as_names)

        # cache
        self._assignment_details = []

    @property
    def end_pos(self):
        return self._token_list[-1].end_pos

    def get_code(self, new_line=True):
        def assemble(command_list, assignment=None):
            pieces = [c.get_code() if isinstance(c, Simple) else c.string if
isinstance(c, (tokenize.Token, Operator)) else unicode(c)
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
        """ Get the names for the statement. """
        if self._set_vars is None:

            def search_calls(calls):
                for call in calls:
                    if isinstance(call, Array):
                        for stmt in call:
                            search_calls(stmt.expression_list())
                    elif isinstance(call, Call):
                        c = call
                        # Check if there's an execution in it, if so this is
                        # not a set_var.
                        is_execution = False
                        while c:
                            if Array.is_type(c.execution, Array.TUPLE):
                                is_execution = True
                            c = c.next
                        if is_execution:
                            continue
                        self._set_vars.append(call.name)

            self._set_vars = []
            for calls, operation in self.assignment_details:
                search_calls(calls)

            if not self.assignment_details and self._names_are_set_vars:
                # In the case of Param, it's also a defining name without ``=``
                search_calls(self.expression_list())
        return self._set_vars + self.as_names

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

        This is not done in the main parser, because it might be slow and
        most of the statements won't need this data anyway. This is something
        'like' a lazy execution.

        This is not really nice written, sorry for that. If you plan to replace
        it and make it nicer, that would be cool :-)
        """
        def is_assignment(tok):
            return isinstance(tok, Operator) and tok.string.endswith('=') \
                and not tok.string in ('>=', '<=', '==', '!=')

        def parse_array(token_iterator, array_type, start_pos, add_el=None):
            arr = Array(self._sub_module, start_pos, array_type, self)
            if add_el is not None:
                arr.add_statement(add_el)
                old_stmt = add_el

            maybe_dict = array_type == Array.SET
            break_tok = None
            is_array = None
            while True:
                stmt, break_tok = parse_stmt(token_iterator, maybe_dict,
                                             break_on_assignment=bool(add_el))
                if stmt is None:
                    break
                else:
                    if break_tok == ',':
                        is_array = True
                    arr.add_statement(stmt, is_key=maybe_dict and break_tok == ':')
                    if break_tok in closing_brackets \
                            or is_assignment(break_tok):
                        break
                old_stmt = stmt
            if arr.type == Array.TUPLE and len(arr) == 1 and not is_array:
                arr.type = Array.NOARRAY
            if not arr.values and maybe_dict:
                # this is a really special case - empty brackets {} are
                # always dictionaries and not sets.
                arr.type = Array.DICT

            arr.end_pos = (break_tok or stmt or old_stmt).end_pos
            return arr, break_tok

        def parse_stmt(token_iterator, maybe_dict=False, added_breaks=(),
                       break_on_assignment=False, stmt_class=Statement,
                       allow_comma=False):
            token_list = []
            level = 0
            first = True
            end_pos = None, None
            tok = None
            for tok in token_iterator:
                end_pos = tok.end_pos
                if first:
                    start_pos = tok.start_pos
                    first = False

                if isinstance(tok, Base):
                    # the token is a Name, which has already been parsed
                    if isinstance(tok, ListComprehension):
                        # it's not possible to set it earlier
                        tok.parent = self
                    elif tok == 'lambda':
                        lambd, tok = parse_lambda(token_iterator)
                        if lambd is not None:
                            token_list.append(lambd)
                    elif tok == 'for':
                        list_comp, tok = parse_list_comp(token_iterator, token_list,
                                                         start_pos, tok.end_pos)
                        if list_comp is not None:
                            token_list = [list_comp]

                    if tok in closing_brackets:
                        level -= 1
                    elif tok in brackets.keys():
                        level += 1

                    if level == -1 or level == 0 and (
                            tok == ',' and not allow_comma
                            or tok in added_breaks
                            or maybe_dict and tok == ':'
                            or is_assignment(tok) and break_on_assignment):
                        end_pos = end_pos[0], end_pos[1] - 1
                        break

                token_list.append(tok)

            if not token_list:
                return None, tok

            statement = stmt_class(self._sub_module, token_list, start_pos,
                                   end_pos, self.parent, set_name_parents=False)
            return statement, tok

        def parse_lambda(token_iterator):
            params = []
            start_pos = self.start_pos
            while True:
                param, tok = parse_stmt(token_iterator, added_breaks=[':'],
                                        stmt_class=Param)
                if param is None:
                    break
                params.append(param)
                if tok == ':':
                    break
            if tok != ':':
                return None, tok

            # Since Lambda is a Function scope, it needs Scope parents.
            parent = self.get_parent_until(IsScope)
            lambd = Lambda(self._sub_module, params, start_pos, parent)

            ret, tok = parse_stmt(token_iterator)
            if ret is not None:
                ret.parent = lambd
                lambd.returns.append(ret)
            lambd.end_pos = self.end_pos
            return lambd, tok

        def parse_list_comp(token_iterator, token_list, start_pos, end_pos):
            def parse_stmt_or_arr(token_iterator, added_breaks=(),
                                  names_are_set_vars=False):
                stmt, tok = parse_stmt(token_iterator, allow_comma=True,
                                       added_breaks=added_breaks)

                if stmt is not None:
                    for t in stmt._token_list:
                        if isinstance(t, Name):
                            t.parent = stmt
                    stmt._names_are_set_vars = names_are_set_vars
                return stmt, tok

            st = Statement(self._sub_module, token_list, start_pos,
                           end_pos, set_name_parents=False)

            middle, tok = parse_stmt_or_arr(token_iterator, ['in'], True)
            if tok != 'in' or middle is None:
                debug.warning('list comprehension middle %s@%s', tok, start_pos)
                return None, tok

            in_clause, tok = parse_stmt_or_arr(token_iterator)
            if in_clause is None:
                debug.warning('list comprehension in @%s', start_pos)
                return None, tok

            return ListComprehension(st, middle, in_clause, self), tok

        # initializations
        result = []
        is_chain = False
        brackets = {'(': Array.TUPLE, '[': Array.LIST, '{': Array.SET}
        closing_brackets = ')', '}', ']'

        token_iterator = iter(self._token_list)
        for tok in token_iterator:
            if isinstance(tok, tokenize.Token):
                token_type = tok.type
                tok_str = tok.string
                if tok_str == 'as':  # just ignore as, because it sets values
                    next(token_iterator, None)
                    continue
            else:
                # the token is a Name, which has already been parsed
                tok_str = tok
                token_type = None

                if is_assignment(tok):
                    # This means, there is an assignment here.
                    # Add assignments, which can be more than one
                    self._assignment_details.append((result, tok.string))
                    result = []
                    is_chain = False
                    continue

            if tok_str == 'lambda':
                lambd, tok_str = parse_lambda(token_iterator)
                if lambd is not None:
                    result.append(lambd)
                if tok_str not in (')', ','):
                    continue

            is_literal = token_type in (tokenize.STRING, tokenize.NUMBER)
            if isinstance(tok_str, Name) or is_literal:
                cls = Literal if is_literal else Call

                call = cls(self._sub_module, tok_str, tok.start_pos, tok.end_pos, self)
                if is_chain:
                    result[-1].set_next(call)
                else:
                    result.append(call)
                is_chain = False
            elif tok_str in brackets.keys():
                arr, is_ass = parse_array(
                    token_iterator, brackets[tok.string], tok.start_pos
                )
                if result and isinstance(result[-1], StatementElement):
                    result[-1].set_execution(arr)
                else:
                    arr.parent = self
                    result.append(arr)
            elif tok_str == '.':
                if result and isinstance(result[-1], StatementElement):
                    is_chain = True
            elif tok_str == ',' and result:  # implies a tuple
                # expression is now an array not a statement anymore
                stmt = Statement(self._sub_module, result, result[0].start_pos,
                                 tok.end_pos, self.parent, set_name_parents=False)
                stmt._expression_list = result
                arr, break_tok = parse_array(token_iterator, Array.TUPLE,
                                             stmt.start_pos, stmt)
                result = [arr]
                if is_assignment(break_tok):
                    self._assignment_details.append((result, break_tok))
                    result = []
                    is_chain = False
            else:
                # comments, strange tokens (like */**), error tokens to
                # reproduce the string correctly.
                is_chain = False
                result.append(tok)
        return result

    def set_expression_list(self, lst):
        """It's necessary for some "hacks" to change the expression_list."""
        self._expression_list = lst


class Param(Statement):
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
    __slots__ = ('parent', 'next', 'execution')

    def __init__(self, module, start_pos, end_pos, parent):
        super(StatementElement, self).__init__(module, start_pos, end_pos)

        # parent is not the oposite of next. The parent of c: a = [b.c] would
        # be an array.
        self.parent = parent
        self.next = None
        self.execution = None

    def set_next(self, call):
        """ Adds another part of the statement"""
        call.parent = self
        if self.next is not None:
            self.next.set_next(call)
        else:
            self.next = call

    def set_execution(self, call):
        """
        An execution is nothing else than brackets, with params in them, which
        shows access on the internals of this name.
        """
        call.parent = self
        if self.next is not None:
            self.next.set_execution(call)
        elif self.execution is not None:
            self.execution.set_execution(call)
        else:
            self.execution = call

    def generate_call_path(self):
        """ Helps to get the order in which statements are executed. """
        try:
            for name_part in self.name.names:
                yield name_part
        except AttributeError:
            yield self
        if self.execution is not None:
            for y in self.execution.generate_call_path():
                yield y
        if self.next is not None:
            for y in self.next.generate_call_path():
                yield y

    def get_code(self):
        s = ''
        if self.execution is not None:
            s += self.execution.get_code()
        if self.next is not None:
            s += '.' + self.next.get_code()
        return s


class Call(StatementElement):
    __slots__ = ('name',)

    def __init__(self, module, name, start_pos, end_pos, parent=None):
        super(Call, self).__init__(module, start_pos, end_pos, parent)
        self.name = name

    def get_code(self):
        return self.name.get_code() + super(Call, self).get_code()

    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, self.name)


class Literal(StatementElement):
    __slots__ = ('literal', 'value')

    def __init__(self, module, literal, start_pos, end_pos, parent=None):
        super(Literal, self).__init__(module, start_pos, end_pos, parent)
        self.literal = literal
        self.value = literal_eval(literal)

    def get_code(self):
        return self.literal + super(Literal, self).get_code()

    def __repr__(self):
        if is_py3:
            s = self.literal
        else:
            s = self.literal.encode('ascii', 'replace')
        return "<%s: %s>" % (type(self).__name__, s)


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


class NamePart(object):
    """
    A string. Sometimes it is important to know if the string belongs to a name
    or not.
    """
    # Unfortunately there's no way to use slots for str (non-zero __itemsize__)
    # -> http://utcc.utoronto.ca/~cks/space/blog/python/IntSlotsPython3k
    # Therefore don't subclass `str`.
    __slots__ = ('parent', '_string', '_line', '_column')

    def __init__(self, string, parent, start_pos):
        self._string = string
        self.parent = parent
        self._line = start_pos[0]
        self._column = start_pos[1]

    def __str__(self):
        return self._string

    def __unicode__(self):
        return self._string

    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, self._string)

    def get_code(self):
        return self._string

    def get_parent_until(self, *args, **kwargs):
        return self.parent.get_parent_until(*args, **kwargs)

    @property
    def start_pos(self):
        offset = self.parent._sub_module.line_offset
        return offset + self._line, self._column

    @property
    def end_pos(self):
        return self.start_pos[0], self.start_pos[1] + len(self._string)


class Name(Simple):
    """
    Used to define names in python.
    Which means the whole namespace/class/function stuff.
    So a name like "module.class.function"
    would result in an array of [module, class, function]
    """
    __slots__ = ('names', '_get_code')

    def __init__(self, module, names, start_pos, end_pos, parent=None):
        super(Name, self).__init__(module, start_pos, end_pos)
        # Cache get_code, because it's used quite often for comparisons
        # (seen by using the profiler).
        self._get_code = ".".join(n[0] for n in names)

        names = tuple(NamePart(n[0], self, n[1]) for n in names)
        self.names = names
        if parent is not None:
            self.parent = parent

    def get_code(self):
        """ Returns the names in a full string format """
        return self._get_code

    @property
    def end_pos(self):
        return self.names[-1].end_pos

    @property
    def docstr(self):
        """Return attribute docstring (PEP 257) if exists."""
        return self.parent.docstr

    def __str__(self):
        return self.get_code()

    def __len__(self):
        return len(self.names)


class ListComprehension(Base):
    """ Helper class for list comprehensions """
    def __init__(self, stmt, middle, input, parent):
        self.stmt = stmt
        self.middle = middle
        self.input = input
        for s in stmt, middle, input:
            s.parent = self
        self.parent = parent

    def get_parent_until(self, *args, **kwargs):
        return Simple.get_parent_until(self, *args, **kwargs)

    @property
    def start_pos(self):
        return self.stmt.start_pos

    @property
    def end_pos(self):
        return self.stmt.end_pos

    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, self.get_code())

    def get_code(self):
        statements = self.stmt, self.middle, self.input
        code = [s.get_code().replace('\n', '') for s in statements]
        return "%s for %s in %s" % tuple(code)


class Operator(Base):
    __slots__ = ('string', '_line', '_column')

    def __init__(self, string, start_pos):
        # TODO needs module param
        self.string = string
        self._line = start_pos[0]
        self._column = start_pos[1]

    def __repr__(self):
        return "<%s: `%s`>" % (type(self).__name__, self.string)

    @property
    def start_pos(self):
        return self._line, self._column

    @property
    def end_pos(self):
        return self._line, self._column + len(self.string)

    def __eq__(self, other):
        """Make comparisons easy. Improves the readability of the parser."""
        return self.string == other

    def __ne__(self, other):
        """Python 2 compatibility."""
        return self.string != other

    def __hash__(self):
        return hash(self.string)
