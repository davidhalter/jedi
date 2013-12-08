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

>>> from jedi.parser import Parser
>>> parser = Parser('import os', 'example.py')
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
from __future__ import with_statement

import os
import re
import tokenizer as tokenize
from inspect import cleandoc
from ast import literal_eval

from jedi._compatibility import next, Python3Method, encoding, unicode, is_py3k
from jedi import common
from jedi import debug


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

    @Python3Method
    def get_parent_until(self, classes=(), reverse=False,
                         include_current=True):
        """ Takes always the parent, until one class (not a Class) """
        if type(classes) not in (tuple, list):
            classes = (classes,)
        scope = self if include_current else self.parent
        while scope.parent is not None:
            if classes and reverse != scope.isinstance(*classes):
                break
            scope = scope.parent
        return scope

    def __repr__(self):
        code = self.get_code().replace('\n', ' ')
        if not is_py3k:
            code = code.encode(encoding, 'replace')
        return "<%s: %s@%s,%s>" % \
            (type(self).__name__, code, self.start_pos[0], self.start_pos[1])


class IsScope(Base):
    pass


class Scope(Simple, IsScope):
    """
    Super class for the parser tree, which represents the state of a python
    text file.
    A Scope manages and owns its subscopes, which are classes and functions, as
    well as variables and imports. It is used to access the structure of python
    files.

    :param start_pos: The position (line and column) of the scope.
    :type start_pos: tuple(int, int)
    """
    def __init__(self, module, start_pos):
        super(Scope, self).__init__(module, start_pos)
        self.subscopes = []
        self.imports = []
        self.statements = []
        self.docstr = ''
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

    def add_docstr(self, string):
        """ Clean up a docstring """
        self.docstr = cleandoc(literal_eval(string))

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

    def get_code(self, first_indent=False, indention='    '):
        """
        :return: Returns the code of the current scope.
        :rtype: str
        """
        string = ""
        if len(self.docstr) > 0:
            string += '"""' + self.docstr + '"""\n'

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
    def get_set_vars(self):
        """
        Get all the names, that are active and accessible in the current
        scope.  See :meth:`get_defined_names` for examples.

        :return: list of Name
        :rtype: list
        """
        n = []
        for stmt in self.statements:
            try:
                n += stmt.get_set_vars(True)
            except TypeError:
                n += stmt.get_set_vars()

        # function and class names
        n += [s.name for s in self.subscopes]

        for i in self.imports:
            if not i.star:
                n += i.get_defined_names()
        return n

    def get_defined_names(self):
        """
        Get all defined names in this scope.

        >>> from jedi.parser import Parser
        >>> parser = Parser('''
        ... a = x
        ... b = y
        ... b.c = z
        ... ''')
        >>> parser.module.get_defined_names()
        [<Name: a@2,0>, <Name: b@3,0>]

        Note that unlike :meth:`get_set_vars`, assignment to object
        attribute does not change the result because it does not change
        the defined names in this scope.

        >>> parser.module.get_set_vars()
        [<Name: a@2,0>, <Name: b@3,0>, <Name: b.c@4,0>]

        """
        return [n for n in self.get_set_vars()
                if isinstance(n, Import) or (len(n) == 1)]

    def is_empty(self):
        """
        :return: True if there are no subscopes, imports and statements.
        :rtype: bool
        """
        return not (self.imports or self.subscopes or self.statements or self.returns)

    @Python3Method
    def get_statement_for_position(self, pos, include_imports=False):
        checks = self.statements + self.asserts
        if include_imports:
            checks += self.imports
        if self.isinstance(Function):
            checks += self.params + self.decorators
            checks += [r for r in self.returns if r is not None]

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
        self._name = None
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

    def get_set_vars(self):
        n = super(SubModule, self).get_set_vars()
        n += self.global_vars
        return n

    @property
    def name(self):
        """ This is used for the goto functions. """
        if self._name is not None:
            return self._name
        if self.path is None:
            string = ''  # no path -> empty name
        else:
            sep = (re.escape(os.path.sep),) * 2
            r = re.search(r'([^%s]*?)(%s__init__)?(\.py|\.so)?$' % sep,
                          self.path)
            # remove PEP 3149 names
            string = re.sub('\.[a-z]+-\d{2}[mud]{0,3}$', '', r.group(1))
        # positions are not real therefore choose (0, 0)
        names = [(string, (0, 0))]
        self._name = Name(self, names, (0, 0), (0, 0), self.use_as_parent)
        return self._name

    def is_builtin(self):
        return not (self.path is None or self.path.endswith('.py'))

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
            if namespace == "__future__" and feature == "absolute_import":
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
        if self.is_empty():
            if self.docstr:
                string += indention
            string += "pass\n"
        return string

    @property
    def doc(self):
        """
        Return a document string including call signature of __init__.
        """
        for sub in self.subscopes:
            if sub.name.names[-1] == '__init__':
                return '%s\n\n%s' % (
                    sub.get_call_signature(funcname=self.name.names[-1]),
                    self.docstr)
        return self.docstr


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
        if self.is_empty():
            if self.docstr:
                string += indention
            string += 'pass\n'
        return string

    def get_set_vars(self):
        n = super(Function, self).get_set_vars()
        for p in self.params:
            try:
                n.append(p.get_name())
            except IndexError:
                debug.warning("multiple names in param %s" % n)
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
        l = (funcname or self.name.names[-1]) + '('
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
        return '%s\n\n%s' % (self.get_call_signature(), self.docstr)


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

    def get_set_vars(self, is_internal_call=False):
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
                n += s.get_set_vars()
            if self.next:
                n += self.next.get_set_vars(is_internal_call)
            n += super(Flow, self).get_set_vars()
            return n
        else:
            return self.get_parent_until((Class, Function)).get_set_vars()

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
        set_stmt.parent = self.use_as_parent
        self.is_list_comp = is_list_comp

        self.set_vars = set_stmt.get_set_vars()
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
        for n in [namespace, alias, from_ns]:
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
            ns_str = str(namespace)

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
            n = Name(self._sub_module, [(o.names[0], o.start_pos)],
                     o.start_pos, o.end_pos, parent=o.parent)
            return [n]
        else:
            return [self.namespace]

    def get_set_vars(self):
        return self.get_defined_names()

    def get_all_import_names(self):
        n = []
        if self.from_ns:
            n.append(self.from_ns)
        if self.namespace:
            n.append(self.namespace)
        if self.alias:
            n.append(self.alias)
        return n


class Statement(Simple):
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
    __slots__ = ('token_list', '_set_vars', 'as_names', '_commands',
                 '_assignment_details', 'docstr', '_names_are_set_vars')

    def __init__(self, module, token_list, start_pos, end_pos, parent=None,
                 as_names=(), names_are_set_vars=False, set_name_parents=True):
        super(Statement, self).__init__(module, start_pos, end_pos)
        if isinstance(start_pos, list):
            raise NotImplementedError()
        self.token_list = token_list
        self._names_are_set_vars = names_are_set_vars
        if set_name_parents:
            for t in token_list:
                if isinstance(t, Name):
                    t.parent = self.use_as_parent
            for n in as_names:
                n.parent = self.use_as_parent
        self.parent = parent
        self.docstr = ''
        self._set_vars = None
        self.as_names = list(as_names)

        # cache
        self._commands = None
        self._assignment_details = []
        # this is important for other scripts

    def add_docstr(self, string):
        """ Clean up a docstring """
        self.docstr = cleandoc(literal_eval(string))

    def get_code(self, new_line=True):
        def assemble(command_list, assignment=None):
            pieces = [c.get_code() if isinstance(c, Simple) else unicode(c)
                      for c in command_list]
            if assignment is None:
                return ''.join(pieces)
            return '%s %s ' % (''.join(pieces), assignment)

        code = ''.join(assemble(*a) for a in self.assignment_details)
        code += assemble(self.get_commands())
        if self.docstr:
            code += '\n"""%s"""' % self.docstr

        if new_line:
            return code + '\n'
        else:
            return code

    def get_set_vars(self):
        """ Get the names for the statement. """
        if self._set_vars is None:
            self._set_vars = []
            def search_calls(calls):
                for call in calls:
                    if isinstance(call, Array):
                        for stmt in call:
                            search_calls(stmt.get_commands())
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

            for calls, operation in self.assignment_details:
                search_calls(calls)

            if not self.assignment_details and self._names_are_set_vars:
                # In the case of Param, it's also a defining name without ``=``
                search_calls(self.get_commands())
        return self._set_vars + self.as_names

    def is_global(self):
        # first keyword of the first token is global -> must be a global
        return str(self.token_list[0]) == "global"

    @property
    def assignment_details(self):
        """
        Returns an array of tuples of the elements before the assignment.

        For example the following code::

            x = (y, z) = 2, ''

        would result in ``[(Name(x), '='), (Array([Name(y), Name(z)]), '=')]``.
        """
        # parse statement which creates the assignment details.
        self.get_commands()
        return self._assignment_details

    def get_commands(self):
        if self._commands is None:
            self._commands = ['time neeeeed']  # avoid recursions
            self._commands = self._parse_statement()
        return self._commands

    def _parse_statement(self):
        """
        This is not done in the main parser, because it might be slow and
        most of the statements won't need this data anyway. This is something
        'like' a lazy execution.

        This is not really nice written, sorry for that. If you plan to replace
        it and make it nicer, that would be cool :-)
        """
        def is_assignment(tok):
            return isinstance(tok, (str, unicode)) and tok.endswith('=') \
                and not tok in ['>=', '<=', '==', '!=']

        def parse_array(token_iterator, array_type, start_pos, add_el=None,
                        added_breaks=()):
            arr = Array(self._sub_module, start_pos, array_type, self)
            if add_el is not None:
                arr.add_statement(add_el)

            maybe_dict = array_type == Array.SET
            break_tok = None
            is_array = None
            while True:
                stmt, break_tok = parse_stmt(token_iterator, maybe_dict,
                                             break_on_assignment=bool(add_el),
                                             added_breaks=added_breaks)
                if stmt is None:
                    break
                else:
                    if break_tok == ',':
                        is_array = True
                    is_key = maybe_dict and break_tok == ':'
                    arr.add_statement(stmt, is_key)
                    if break_tok in closing_brackets \
                            or break_tok in added_breaks \
                            or is_assignment(break_tok):
                        break
            if arr.type == Array.TUPLE and len(arr) == 1 and not is_array:
                arr.type = Array.NOARRAY
            if not arr.values and maybe_dict:
                # this is a really special case - empty brackets {} are
                # always dictionaries and not sets.
                arr.type = Array.DICT

            c = token_iterator.current[1]
            arr.end_pos = c.end_pos if isinstance(c, Simple) \
                else c.end_pos
            return arr, break_tok

        def parse_stmt(token_iterator, maybe_dict=False, added_breaks=(),
                       break_on_assignment=False, stmt_class=Statement):
            token_list = []
            level = 1
            tok = None
            first = True
            end_pos = None, None
            for i, tok_temp in token_iterator:
                if isinstance(tok_temp, Base):
                    # the token is a Name, which has already been parsed
                    tok = tok_temp
                    if first:
                        start_pos = tok.start_pos
                        first = False
                    end_pos = tok.end_pos
                    if isinstance(tok, ListComprehension):
                        # it's not possible to set it earlier
                        tok.parent = self
                else:
                    tok           = tok_temp.token
                    start_tok_pos = tok_temp.start_pos
                    last_end_pos  = end_pos
                    end_pos       = tok_temp.end_pos
                    if first:
                        first = False
                        start_pos = start_tok_pos

                    if tok == 'lambda':
                        lambd, tok = parse_lambda(token_iterator)
                        if lambd is not None:
                            token_list.append(lambd)
                    elif tok == 'for':
                        list_comp, tok = parse_list_comp(
                            token_iterator,
                            token_list,
                            start_pos,
                            last_end_pos
                        )
                        if list_comp is not None:
                            token_list = [list_comp]

                    if tok in closing_brackets:
                        level -= 1
                    elif tok in brackets.keys():
                        level += 1

                    if level == 0 and tok in closing_brackets \
                            or tok in added_breaks \
                            or level == 1 and (
                                tok == ','
                                or maybe_dict and tok == ':'
                                or is_assignment(tok)
                                and break_on_assignment
                            ):
                        end_pos = end_pos[0], end_pos[1] - 1
                        break
                token_list.append(tok_temp)

            if not token_list:
                return None, tok

            statement = stmt_class(
                self._sub_module,
                token_list,
                start_pos,
                end_pos,
                self.parent,
                set_name_parents=False
            )
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

            # since lambda is a Function scope, it needs Scope parents
            parent = self.get_parent_until(IsScope)
            lambd = Lambda(self._sub_module, params, start_pos, parent)

            ret, tok = parse_stmt(token_iterator)
            if ret is not None:
                ret.parent = lambd
                lambd.returns.append(ret)
            lambd.end_pos = self.end_pos
            return lambd, tok

        def parse_list_comp(token_iterator, token_list, start_pos, end_pos):
            def parse_stmt_or_arr(
                token_iterator, added_breaks=(), names_are_set_vars=False
            ):
                stmt, tok = parse_stmt(token_iterator,
                                       added_breaks=added_breaks)
                if not stmt:
                    return None, tok
                if tok == ',':
                    arr, tok = parse_array(token_iterator, Array.TUPLE,
                                           stmt.start_pos, stmt,
                                           added_breaks=added_breaks)
                    token_list = []
                    for stmt in arr:
                        token_list += stmt.token_list
                    start_pos = arr.start_pos[0], arr.start_pos[1] - 1
                    stmt = Statement(self._sub_module, token_list,
                                     start_pos, arr.end_pos)
                    arr.parent = stmt
                    stmt.token_list = stmt._commands = [arr]
                else:
                    for t in stmt.token_list:
                        if isinstance(t, Name):
                            t.parent = stmt
                stmt._names_are_set_vars = names_are_set_vars
                return stmt, tok

            st = Statement(self._sub_module, token_list, start_pos,
                           end_pos, set_name_parents=False)

            middle, tok = parse_stmt_or_arr(token_iterator, ['in'], True)
            if tok != 'in' or middle is None:
                debug.warning('list comprehension middle @%s' % str(start_pos))
                return None, tok

            in_clause, tok = parse_stmt_or_arr(token_iterator)
            if in_clause is None:
                debug.warning('list comprehension in @%s' % str(start_pos))
                return None, tok

            return ListComprehension(st, middle, in_clause, self), tok

        # initializations
        result = []
        is_chain = False
        brackets = {'(': Array.TUPLE, '[': Array.LIST, '{': Array.SET}
        closing_brackets = ')', '}', ']'

        token_iterator = common.PushBackIterator(enumerate(self.token_list))
        for i, tok_temp in token_iterator:
            if isinstance(tok_temp, Base):
                # the token is a Name, which has already been parsed
                tok = tok_temp
                token_type = None
                start_pos = tok.start_pos
                end_pos = tok.end_pos
            else:
                token_type = tok_temp.token_type
                tok        = tok_temp.token
                start_pos  = tok_temp.start_pos
                end_pos    = tok_temp.end_pos
                if is_assignment(tok):
                    # This means, there is an assignment here.
                    # Add assignments, which can be more than one
                    self._assignment_details.append(
                        (result, tok_temp.token)
                    )
                    result = []
                    is_chain = False
                    continue
                elif tok == 'as':  # just ignore as, because it sets values
                    next(token_iterator, None)
                    continue

            if tok == 'lambda':
                lambd, tok = parse_lambda(token_iterator)
                if lambd is not None:
                    result.append(lambd)
                else:
                    continue

            is_literal = token_type in [tokenize.STRING, tokenize.NUMBER]
            if isinstance(tok, Name) or is_literal:
                cls = Call
                if is_literal:
                    cls = String if token_type == tokenize.STRING else Number

                call = cls(self._sub_module, tok, start_pos, end_pos, self)
                if is_chain:
                    result[-1].set_next(call)
                else:
                    result.append(call)
                is_chain = False
            elif tok in brackets.keys():
                arr, is_ass = parse_array(
                    token_iterator, brackets[tok], start_pos
                )
                if result and isinstance(result[-1], StatementElement):
                    result[-1].set_execution(arr)
                else:
                    arr.parent = self
                    result.append(arr)
            elif tok == '.':
                if result and isinstance(result[-1], StatementElement):
                    is_chain = True
            elif tok == ',':  # implies a tuple
                # commands is now an array not a statement anymore
                t = result[0]
                start_pos = t[2] if isinstance(t, tuple) else t.start_pos

                # get the correct index
                i, tok = next(token_iterator, (len(self.token_list), None))
                if tok is not None:
                    token_iterator.push_back((i, tok))
                t = self.token_list[i - 1]
                try:
                    e = t.end_pos
                except AttributeError:
                    e = (t[2][0], t[2][1] + len(t[1])) \
                        if isinstance(t, tuple) else t.start_pos

                stmt = Statement(
                    self._sub_module,
                    result,
                    start_pos,
                    e,
                    self.parent,
                    set_name_parents=False
                )
                stmt._commands = result
                arr, break_tok = parse_array(token_iterator, Array.TUPLE,
                                             stmt.start_pos, stmt)
                result = [arr]
                if is_assignment(break_tok):
                    self._assignment_details.append((result, break_tok))
                    result = []
                    is_chain = False
            else:
                if tok != '\n' and token_type != tokenize.COMMENT:
                    result.append(tok)
        return result


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
        n = self.get_set_vars()
        if len(n) > 1:
            debug.warning("Multiple param names (%s)." % n)
        return n[0]


class StatementElement(Simple):
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
    def __init__(self, module, name, start_pos, end_pos, parent=None):
        super(Call, self).__init__(module, start_pos, end_pos, parent)
        self.name = name

    def get_code(self):
        return self.name.get_code() + super(Call, self).get_code()

    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, self.name)


class Literal(StatementElement):
    def __init__(self, module, literal, start_pos, end_pos, parent=None):
        super(Literal, self).__init__(module, start_pos, end_pos, parent)
        self.literal = literal
        self.value = literal_eval(literal)

    def get_code(self):
        return self.literal + super(Literal, self).get_code()

    def type_as_string(self):
        return type(self.value).__name__

    def __repr__(self):
        if is_py3k:
            s = self.literal
        else:
            s = self.literal.encode('ascii', 'replace')
        return "<%s: %s>" % (type(self).__name__, s)


class String(Literal):
    pass


class Number(Literal):
    pass


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


class NamePart(str):
    """
    A string. Sometimes it is important to know if the string belongs to a name
    or not.
    """
    # Unfortunately there's no way to use slots for str (non-zero __itemsize__)
    # -> http://utcc.utoronto.ca/~cks/space/blog/python/IntSlotsPython3k
    #__slots__ = ('_start_pos', 'parent')
    def __new__(cls, s, parent, start_pos):
        self = super(NamePart, cls).__new__(cls, s)
        self._start_pos = start_pos
        self.parent = parent
        return self

    @property
    def start_pos(self):
        offset = self.parent._sub_module.line_offset
        return offset + self._start_pos[0], self._start_pos[1]

    @property
    def end_pos(self):
        return self.start_pos[0], self.start_pos[1] + len(self)

    def __getnewargs__(self):
        return str(self), self.parent, self._start_pos


class Name(Simple):
    """
    Used to define names in python.
    Which means the whole namespace/class/function stuff.
    So a name like "module.class.function"
    would result in an array of [module, class, function]
    """
    __slots__ = ('names',)

    def __init__(self, module, names, start_pos, end_pos, parent=None):
        super(Name, self).__init__(module, start_pos, end_pos)
        self.names = tuple(n if isinstance(n, NamePart) else
                           NamePart(n[0], self, n[1]) for n in names)
        if parent is not None:
            self.parent = parent

    def get_code(self):
        """ Returns the names in a full string format """
        return ".".join(self.names)

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
        for s in [stmt, middle, input]:
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
        return "<%s: %s>" % \
            (type(self).__name__, self.get_code())

    def get_code(self):
        statements = self.stmt, self.middle, self.input
        code = [s.get_code().replace('\n', '') for s in statements]
        return "%s for %s in %s" % tuple(code)
