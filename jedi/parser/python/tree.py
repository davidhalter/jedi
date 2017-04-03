"""
If you know what an syntax tree is, you'll see that this module is pretty much
that. The classes represent syntax elements like functions and imports.

This is the "business logic" part of the parser. There's a lot of logic here
that makes it easier for Jedi (and other libraries) to deal with a Python syntax
tree.

By using `get_code` on a module, you can get back the 1-to-1 representation of
the input given to the parser. This is important if you are using refactoring.

The easiest way to play with this module is to use :class:`parsing.Parser`.
:attr:`parsing.Parser.module` holds an instance of :class:`Module`:

>>> from jedi.parser.python import parse
>>> parser = parse('import os')
>>> module = parser.get_root_node()
>>> module
<Module: @1-1>

Any subclasses of :class:`Scope`, including :class:`Module` has an attribute
:attr:`imports <Scope.imports>`:

>>> module.imports
[<ImportName: import os@1,0>]

See also :attr:`Scope.subscopes` and :attr:`Scope.statements`.

For static analysis purposes there exists a method called
``nodes_to_execute`` on all nodes and leaves. It's documented in the static
anaylsis documentation.
"""

from inspect import cleandoc
from itertools import chain
import textwrap
import abc

from jedi._compatibility import (Python3Method, is_py3, utf8_repr,
                                 literal_eval, unicode)
from jedi.parser.tree import Node, BaseNode, Leaf, ErrorNode, ErrorLeaf


def _safe_literal_eval(value):
    first_two = value[:2].lower()
    if first_two[0] == 'f' or first_two in ('fr', 'rf'):
        # literal_eval is not able to resovle f literals. We have to do that
        # manually in a later stage
        return ''

    try:
        return literal_eval(value)
    except SyntaxError:
        # It's possible to create syntax errors with literals like rb'' in
        # Python 2. This should not be possible and in that case just return an
        # empty string.
        # Before Python 3.3 there was a more strict definition in which order
        # you could define literals.
        return ''


def search_ancestor(node, node_type_or_types):
    if not isinstance(node_type_or_types, (list, tuple)):
        node_type_or_types = (node_type_or_types,)

    while True:
        node = node.parent
        if node is None or node.type in node_type_or_types:
            return node


class DocstringMixin(object):
    __slots__ = ()

    @property
    def raw_doc(self):
        """ Returns a cleaned version of the docstring token. """
        if self.type == 'file_input':
            node = self.children[0]
        elif isinstance(self, ClassOrFunc):
            node = self.children[self.children.index(':') + 1]
            if node.type == 'suite':  # Normally a suite
                node = node.children[1]  # -> NEWLINE stmt
        else:  # ExprStmt
            simple_stmt = self.parent
            c = simple_stmt.parent.children
            index = c.index(simple_stmt)
            if not index:
                return ''
            node = c[index - 1]

        if node.type == 'simple_stmt':
            node = node.children[0]

        if node.type == 'string':
            # TODO We have to check next leaves until there are no new
            # leaves anymore that might be part of the docstring. A
            # docstring can also look like this: ``'foo' 'bar'
            # Returns a literal cleaned version of the ``Token``.
            cleaned = cleandoc(_safe_literal_eval(node.value))
            # Since we want the docstr output to be always unicode, just
            # force it.
            if is_py3 or isinstance(cleaned, unicode):
                return cleaned
            else:
                return unicode(cleaned, 'UTF-8', 'replace')
        return ''


class PythonMixin():
    def get_parent_scope(self, include_flows=False):
        """
        Returns the underlying scope.
        """
        scope = self.parent
        while scope is not None:
            if include_flows and isinstance(scope, Flow):
                return scope
            if scope.is_scope():
                break
            scope = scope.parent
        return scope

    def get_definition(self):
        if self.type in ('newline', 'endmarker'):
            raise ValueError('Cannot get the indentation of whitespace or indentation.')
        scope = self
        while scope.parent is not None:
            parent = scope.parent
            if isinstance(scope, (PythonNode, PythonLeaf)) and parent.type != 'simple_stmt':
                if scope.type == 'testlist_comp':
                    try:
                        if scope.children[1].type == 'comp_for':
                            return scope.children[1]
                    except IndexError:
                        pass
                scope = parent
            else:
                break
        return scope

    def is_scope(self):
        # Default is not being a scope. Just inherit from Scope.
        return False

    @abc.abstractmethod
    def nodes_to_execute(self, last_added=False):
        raise NotImplementedError()

    @Python3Method
    def name_for_position(self, position):
        for c in self.children:
            if isinstance(c, Leaf):
                if isinstance(c, Name) and c.start_pos <= position <= c.end_pos:
                    return c
            else:
                result = c.name_for_position(position)
                if result is not None:
                    return result
        return None

    @Python3Method
    def get_statement_for_position(self, pos):
        for c in self.children:
            if c.start_pos <= pos <= c.end_pos:
                if c.type not in ('decorated', 'simple_stmt', 'suite') \
                        and not isinstance(c, (Flow, ClassOrFunc)):
                    return c
                else:
                    try:
                        return c.get_statement_for_position(pos)
                    except AttributeError:
                        pass  # Must be a non-scope
        return None


class PythonLeaf(Leaf, PythonMixin):
    __slots__ = ()


class _LeafWithoutNewlines(PythonLeaf):
    """
    Simply here to optimize performance.
    """
    __slots__ = ()

    @property
    def end_pos(self):
        return self.line, self.indent + len(self.value)


# Python base classes
class PythonBaseNode(BaseNode, PythonMixin):
    __slots__ = ()


class PythonNode(Node, PythonMixin):
    __slots__ = ()


class PythonErrorNode(ErrorNode, PythonMixin):
    __slots__ = ()


class PythonErrorLeaf(ErrorLeaf, PythonMixin):
    __slots__ = ()


class EndMarker(_LeafWithoutNewlines):
    __slots__ = ()
    type = 'endmarker'


class Newline(PythonLeaf):
    """Contains NEWLINE and ENDMARKER tokens."""
    __slots__ = ()
    type = 'newline'

    @utf8_repr
    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, repr(self.value))


class Name(_LeafWithoutNewlines):
    """
    A string. Sometimes it is important to know if the string belongs to a name
    or not.
    """
    type = 'name'
    __slots__ = ()

    def __str__(self):
        return self.value

    def __unicode__(self):
        return self.value

    def __repr__(self):
        return "<%s: %s@%s,%s>" % (type(self).__name__, self.value,
                                   self.line, self.indent)

    def is_definition(self):
        if self.parent.type in ('power', 'atom_expr'):
            # In `self.x = 3` self is not a definition, but x is.
            return False

        stmt = self.get_definition()
        if stmt.type in ('funcdef', 'classdef', 'param'):
            return self == stmt.name
        elif stmt.type == 'for_stmt':
            return self.start_pos < stmt.children[2].start_pos
        elif stmt.type == 'try_stmt':
            return self.get_previous_sibling() == 'as'
        else:
            return stmt.type in ('expr_stmt', 'import_name', 'import_from',
                                 'comp_for', 'with_stmt') \
                and self in stmt.get_defined_names()

    def nodes_to_execute(self, last_added=False):
        if last_added is False:
            yield self


class Literal(PythonLeaf):
    __slots__ = ()

    def eval(self):
        return _safe_literal_eval(self.value)


class Number(Literal):
    type = 'number'
    __slots__ = ()


class String(Literal):
    type = 'string'
    __slots__ = ()


class Operator(_LeafWithoutNewlines):
    type = 'operator'
    __slots__ = ()

    def __str__(self):
        return self.value

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


class Keyword(_LeafWithoutNewlines):
    type = 'keyword'
    __slots__ = ()

    def __eq__(self, other):
        """
        Make comparisons with strings easy.
        Improves the readability of the parser.
        """
        if isinstance(other, Keyword):
            return self is other
        return self.value == other

    def __ne__(self, other):
        """Python 2 compatibility."""
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.value)


class Scope(PythonBaseNode, DocstringMixin):
    """
    Super class for the parser tree, which represents the state of a python
    text file.
    A Scope manages and owns its subscopes, which are classes and functions, as
    well as variables and imports. It is used to access the structure of python
    files.

    :param start_pos: The position (line and column) of the scope.
    :type start_pos: tuple(int, int)
    """
    __slots__ = ()

    def __init__(self, children):
        super(Scope, self).__init__(children)

    @property
    def returns(self):
        # Needed here for fast_parser, because the fast_parser splits and
        # returns will be in "normal" modules.
        return self._search_in_scope(ReturnStmt)

    @property
    def subscopes(self):
        return self._search_in_scope(Scope)

    @property
    def flows(self):
        return self._search_in_scope(Flow)

    @property
    def imports(self):
        return self._search_in_scope(Import)

    @Python3Method
    def _search_in_scope(self, typ):
        def scan(children):
            elements = []
            for element in children:
                if isinstance(element, typ):
                    elements.append(element)
                if element.type in ('suite', 'simple_stmt', 'decorated') \
                        or isinstance(element, Flow):
                    elements += scan(element.children)
            return elements

        return scan(self.children)

    @property
    def statements(self):
        return self._search_in_scope((ExprStmt, KeywordStatement))

    def is_scope(self):
        return True

    def __repr__(self):
        try:
            name = self.name
        except AttributeError:
            name = ''

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


class Module(Scope):
    """
    The top scope, which is always a module.
    Depending on the underlying parser this may be a full module or just a part
    of a module.
    """
    __slots__ = ('_used_names',)
    type = 'file_input'

    def __init__(self, children):
        super(Module, self).__init__(children)
        self._used_names = None

    @property
    def has_explicit_absolute_import(self):
        """
        Checks if imports in this module are explicitly absolute, i.e. there
        is a ``__future__`` import.
        """
        # TODO this is a strange scan and not fully correct. I think Python's
        # parser does it in a different way and scans for the first
        # statement/import with a tokenizer (to check for syntax changes like
        # the future print statement).
        for imp in self.imports:
            if imp.type == 'import_from' and imp.level == 0:
                for path in imp.paths():
                    if [str(name) for name in path] == ['__future__', 'absolute_import']:
                        return True
        return False

    def nodes_to_execute(self, last_added=False):
        # Yield itself, class needs to be executed for decorator checks.
        result = []
        for child in self.children:
            result += child.nodes_to_execute()
        return result

    @property
    def used_names(self):
        if self._used_names is None:
            # Don't directly use self._used_names to eliminate a lookup.
            dct = {}

            def recurse(node):
                try:
                    children = node.children
                except AttributeError:
                    if node.type == 'name':
                        arr = dct.setdefault(node.value, [])
                        arr.append(node)
                else:
                    for child in children:
                        recurse(child)

            recurse(self)
            self._used_names = dct
        return self._used_names


class Decorator(PythonBaseNode):
    type = 'decorator'
    __slots__ = ()

    def nodes_to_execute(self, last_added=False):
        if self.children[-2] == ')':
            node = self.children[-3]
            if node != '(':
                return node.nodes_to_execute()
        return []


class ClassOrFunc(Scope):
    __slots__ = ()

    @property
    def name(self):
        return self.children[1]

    def get_decorators(self):
        decorated = self.parent
        if decorated.type == 'decorated':
            if decorated.children[0].type == 'decorators':
                return decorated.children[0].children
            else:
                return decorated.children[:1]
        else:
            return []


class Class(ClassOrFunc):
    """
    Used to store the parsed contents of a python class.

    :param name: The Class name.
    :type name: str
    :param supers: The super classes of a Class.
    :type supers: list
    :param start_pos: The start position (line, column) of the class.
    :type start_pos: tuple(int, int)
    """
    type = 'classdef'
    __slots__ = ()

    def __init__(self, children):
        super(Class, self).__init__(children)

    def get_super_arglist(self):
        if self.children[2] != '(':  # Has no parentheses
            return None
        else:
            if self.children[3] == ')':  # Empty parentheses
                return None
            else:
                return self.children[3]

    @property
    def doc(self):
        """
        Return a document string including call signature of __init__.
        """
        docstr = self.raw_doc
        for sub in self.subscopes:
            if str(sub.name) == '__init__':
                return '%s\n\n%s' % (
                    sub.get_call_signature(func_name=self.name), docstr)
        return docstr

    def nodes_to_execute(self, last_added=False):
        # Yield itself, class needs to be executed for decorator checks.
        yield self
        # Super arguments.
        arglist = self.get_super_arglist()
        try:
            children = arglist.children
        except AttributeError:
            if arglist is not None:
                for node_to_execute in arglist.nodes_to_execute():
                    yield node_to_execute
        else:
            for argument in children:
                if argument.type == 'argument':
                    # metaclass= or list comprehension or */**
                    raise NotImplementedError('Metaclasses not implemented')
                else:
                    for node_to_execute in argument.nodes_to_execute():
                        yield node_to_execute

        # care for the class suite:
        for node in self.children[self.children.index(':'):]:
            # This could be easier without the fast parser. But we need to find
            # the position of the colon, because everything after it can be a
            # part of the class, not just its suite.
            for node_to_execute in node.nodes_to_execute():
                yield node_to_execute


def _create_params(parent, argslist_list):
    """
    `argslist_list` is a list that can contain an argslist as a first item, but
    most not. It's basically the items between the parameter brackets (which is
    at most one item).
    This function modifies the parser structure. It generates `Param` objects
    from the normal ast. Those param objects do not exist in a normal ast, but
    make the evaluation of the ast tree so much easier.
    You could also say that this function replaces the argslist node with a
    list of Param objects.
    """
    def check_python2_nested_param(node):
        """
        Python 2 allows params to look like ``def x(a, (b, c))``, which is
        basically a way of unpacking tuples in params. Python 3 has ditched
        this behavior. Jedi currently just ignores those constructs.
        """
        return node.type == 'tfpdef' and node.children[0] == '('

    try:
        first = argslist_list[0]
    except IndexError:
        return []

    if first.type in ('name', 'tfpdef'):
        if check_python2_nested_param(first):
            return [first]
        else:
            return [Param([first], parent)]
    elif first == '*':
        return [first]
    else:  # argslist is a `typedargslist` or a `varargslist`.
        children = first.children
        new_children = []
        start = 0
        # Start with offset 1, because the end is higher.
        for end, child in enumerate(children + [None], 1):
            if child is None or child == ',':
                param_children = children[start:end]
                if param_children:  # Could as well be comma and then end.
                    if check_python2_nested_param(param_children[0]):
                        new_children += param_children
                    elif param_children[0] == '*' and param_children[1] == ',':
                        new_children += param_children
                    else:
                        new_children.append(Param(param_children, parent))
                    start = end
        return new_children


class Function(ClassOrFunc):
    """
    Used to store the parsed contents of a python function.

    Children:
      0) <Keyword: def>
      1) <Name>
      2) parameter list (including open-paren and close-paren <Operator>s)
      3 or 5) <Operator: :>
      4 or 6) Node() representing function body
      3) -> (if annotation is also present)
      4) annotation (if present)
    """
    type = 'funcdef'

    def __init__(self, children):
        super(Function, self).__init__(children)
        parameters = self.children[2]  # After `def foo`
        parameters.children[1:-1] = _create_params(parameters, parameters.children[1:-1])

    @property
    def params(self):
        return [p for p in self.children[2].children if p.type == 'param']

    @property
    def name(self):
        return self.children[1]  # First token after `def`

    @property
    def yields(self):
        # TODO This is incorrect, yields are also possible in a statement.
        return self._search_in_scope(YieldExpr)

    def is_generator(self):
        return bool(self.yields)

    def annotation(self):
        try:
            if self.children[3] == "->":
                return self.children[4]
            assert self.children[3] == ":"
            return None
        except IndexError:
            return None

    def get_call_signature(self, width=72, func_name=None):
        """
        Generate call signature of this function.

        :param width: Fold lines if a line is longer than this value.
        :type width: int
        :arg func_name: Override function name when given.
        :type func_name: str

        :rtype: str
        """
        func_name = func_name or self.name
        code = unicode(func_name) + self._get_paramlist_code()
        return '\n'.join(textwrap.wrap(code, width))

    def _get_paramlist_code(self):
        return self.children[2].get_code()

    @property
    def doc(self):
        """ Return a document string including call signature. """
        docstr = self.raw_doc
        return '%s\n\n%s' % (self.get_call_signature(), docstr)

    def nodes_to_execute(self, last_added=False):
        # Yield itself, functions needs to be executed for decorator checks.
        yield self
        for param in self.params:
            if param.default is not None:
                yield param.default
        # care for the function suite:
        for node in self.children[4:]:
            # This could be easier without the fast parser. The fast parser
            # allows that the 4th position is empty or that there's even a
            # fifth element (another function/class). So just scan everything
            # after colon.
            for node_to_execute in node.nodes_to_execute():
                yield node_to_execute


class Lambda(Function):
    """
    Lambdas are basically trimmed functions, so give it the same interface.

    Children:
       0) <Keyword: lambda>
       *) <Param x> for each argument x
      -2) <Operator: :>
      -1) Node() representing body
    """
    type = 'lambda'
    __slots__ = ()

    def __init__(self, children):
        # We don't want to call the Function constructor, call its parent.
        super(Function, self).__init__(children)
        lst = self.children[1:-2]  # Everything between `lambda` and the `:` operator is a parameter.
        self.children[1:-2] = _create_params(self, lst)

    @property
    def name(self):
        # Borrow the position of the <Keyword: lambda> AST node.
        return Name('<lambda>', self.children[0].start_pos)

    def _get_paramlist_code(self):
        return '(' + ''.join(param.get_code() for param in self.params).strip() + ')'

    @property
    def params(self):
        return self.children[1:-2]

    def is_generator(self):
        return False

    def annotation(self):
        # lambda functions do not support annotations
        return None

    @property
    def yields(self):
        return []

    def nodes_to_execute(self, last_added=False):
        for param in self.params:
            if param.default is not None:
                yield param.default
        # Care for the lambda test (last child):
        for node_to_execute in self.children[-1].nodes_to_execute():
            yield node_to_execute

    def __repr__(self):
        return "<%s@%s>" % (self.__class__.__name__, self.start_pos)


class Flow(PythonBaseNode):
    __slots__ = ()
    FLOW_KEYWORDS = (
        'try', 'except', 'finally', 'else', 'if', 'elif', 'with', 'for', 'while'
    )

    def nodes_to_execute(self, last_added=False):
        for child in self.children:
            for node_to_execute in child.nodes_to_execute():
                yield node_to_execute

    def get_branch_keyword(self, node):
        start_pos = node.start_pos
        if not (self.start_pos < start_pos <= self.end_pos):
            raise ValueError('The node is not part of the flow.')

        keyword = None
        for i, child in enumerate(self.children):
            if start_pos < child.start_pos:
                return keyword
            first_leaf = child.get_first_leaf()
            if first_leaf in self.FLOW_KEYWORDS:
                keyword = first_leaf
        return 0


class IfStmt(Flow):
    type = 'if_stmt'
    __slots__ = ()

    def check_nodes(self):
        """
        Returns all the `test` nodes that are defined as x, here:

            if x:
                pass
            elif x:
                pass
        """
        for i, c in enumerate(self.children):
            if c in ('elif', 'if'):
                yield self.children[i + 1]

    def node_in_which_check_node(self, node):
        """
        Returns the check node (see function above) that a node is contained
        in. However if it the node is in the check node itself and not in the
        suite return None.
        """
        start_pos = node.start_pos
        for check_node in reversed(list(self.check_nodes())):
            if check_node.start_pos < start_pos:
                if start_pos < check_node.end_pos:
                    return None
                    # In this case the node is within the check_node itself,
                    # not in the suite
                else:
                    return check_node

    def node_after_else(self, node):
        """
        Checks if a node is defined after `else`.
        """
        for c in self.children:
            if c == 'else':
                if node.start_pos > c.start_pos:
                    return True
        else:
            return False


class WhileStmt(Flow):
    type = 'while_stmt'
    __slots__ = ()


class ForStmt(Flow):
    type = 'for_stmt'
    __slots__ = ()

    def get_input_node(self):
        """
        Returns the input node ``y`` from: ``for x in y:``.
        """
        return self.children[3]

    def defines_one_name(self):
        """
        Returns True if only one name is returned: ``for x in y``.
        Returns False if the for loop is more complicated: ``for x, z in y``.

        :returns: bool
        """
        return self.children[1].type == 'name'


class TryStmt(Flow):
    type = 'try_stmt'
    __slots__ = ()

    def except_clauses(self):
        """
        Returns the ``test`` nodes found in ``except_clause`` nodes.
        Returns ``[None]`` for except clauses without an exception given.
        """
        for node in self.children:
            if node.type == 'except_clause':
                yield node.children[1]
            elif node == 'except':
                yield None

    def nodes_to_execute(self, last_added=False):
        result = []
        for child in self.children[2::3]:
            result += child.nodes_to_execute()
        for child in self.children[0::3]:
            if child.type == 'except_clause':
                # Add the test node and ignore the `as NAME` definition.
                result += child.children[1].nodes_to_execute()
        return result


class WithStmt(Flow):
    type = 'with_stmt'
    __slots__ = ()

    def get_defined_names(self):
        names = []
        for with_item in self.children[1:-2:2]:
            # Check with items for 'as' names.
            if with_item.type == 'with_item':
                names += _defined_names(with_item.children[2])
        return names

    def node_from_name(self, name):
        node = name
        while True:
            node = node.parent
            if node.type == 'with_item':
                return node.children[0]

    def nodes_to_execute(self, last_added=False):
        result = []
        for child in self.children[1::2]:
            if child.type == 'with_item':
                # Just ignore the `as EXPR` part - at least for now, because
                # most times it's just a name.
                child = child.children[0]
            result += child.nodes_to_execute()
        return result


class Import(PythonBaseNode):
    __slots__ = ()

    def path_for_name(self, name):
        try:
            # The name may be an alias. If it is, just map it back to the name.
            name = self.aliases()[name]
        except KeyError:
            pass

        for path in self.paths():
            if name in path:
                return path[:path.index(name) + 1]
        raise ValueError('Name should be defined in the import itself')

    def is_nested(self):
        return False  # By default, sub classes may overwrite this behavior

    def is_star_import(self):
        return self.children[-1] == '*'

    def nodes_to_execute(self, last_added=False):
        """
        `nodes_to_execute` works a bit different for imports, because the names
        itself cannot directly get resolved (except on itself).
        """
        # TODO couldn't we return the names? Would be nicer.
        return [self]


class ImportFrom(Import):
    type = 'import_from'
    __slots__ = ()

    def get_defined_names(self):
        return [alias or name for name, alias in self._as_name_tuples()]

    def aliases(self):
        """Mapping from alias to its corresponding name."""
        return dict((alias, name) for name, alias in self._as_name_tuples()
                    if alias is not None)

    def get_from_names(self):
        for n in self.children[1:]:
            if n not in ('.', '...'):
                break
        if n.type == 'dotted_name':  # from x.y import
            return n.children[::2]
        elif n == 'import':  # from . import
            return []
        else:  # from x import
            return [n]

    @property
    def level(self):
        """The level parameter of ``__import__``."""
        level = 0
        for n in self.children[1:]:
            if n in ('.', '...'):
                level += len(n.value)
            else:
                break
        return level

    def _as_name_tuples(self):
        last = self.children[-1]
        if last == ')':
            last = self.children[-2]
        elif last == '*':
            return  # No names defined directly.

        if last.type == 'import_as_names':
            as_names = last.children[::2]
        else:
            as_names = [last]
        for as_name in as_names:
            if as_name.type == 'name':
                yield as_name, None
            else:
                yield as_name.children[::2]  # yields x, y -> ``x as y``

    def star_import_name(self):
        """
        The last name defined in a star import.
        """
        return self.paths()[-1][-1]

    def paths(self):
        """
        The import paths defined in an import statement. Typically an array
        like this: ``[<Name: datetime>, <Name: date>]``.
        """
        dotted = self.get_from_names()

        if self.children[-1] == '*':
            return [dotted]
        return [dotted + [name] for name, alias in self._as_name_tuples()]


class ImportName(Import):
    """For ``import_name`` nodes. Covers normal imports without ``from``."""
    type = 'import_name'
    __slots__ = ()

    def get_defined_names(self):
        return [alias or path[0] for path, alias in self._dotted_as_names()]

    @property
    def level(self):
        """The level parameter of ``__import__``."""
        return 0  # Obviously 0 for imports without from.

    def paths(self):
        return [path for path, alias in self._dotted_as_names()]

    def _dotted_as_names(self):
        """Generator of (list(path), alias) where alias may be None."""
        dotted_as_names = self.children[1]
        if dotted_as_names.type == 'dotted_as_names':
            as_names = dotted_as_names.children[::2]
        else:
            as_names = [dotted_as_names]

        for as_name in as_names:
            if as_name.type == 'dotted_as_name':
                alias = as_name.children[2]
                as_name = as_name.children[0]
            else:
                alias = None
            if as_name.type == 'name':
                yield [as_name], alias
            else:
                # dotted_names
                yield as_name.children[::2], alias

    def is_nested(self):
        """
        This checks for the special case of nested imports, without aliases and
        from statement::

            import foo.bar
        """
        return [1 for path, alias in self._dotted_as_names()
                if alias is None and len(path) > 1]

    def aliases(self):
        return dict((alias, path[-1]) for path, alias in self._dotted_as_names()
                    if alias is not None)


class KeywordStatement(PythonBaseNode):
    """
    For the following statements: `assert`, `del`, `global`, `nonlocal`,
    `raise`, `return`, `yield`, `return`, `yield`.

    `pass`, `continue` and `break` are not in there, because they are just
    simple keywords and the parser reduces it to a keyword.
    """
    __slots__ = ()

    @property
    def type(self):
        """
        Keyword statements start with the keyword and end with `_stmt`. You can
        crosscheck this with the Python grammar.
        """
        return '%s_stmt' % self.keyword

    @property
    def keyword(self):
        return self.children[0].value

    def nodes_to_execute(self, last_added=False):
        result = []
        for child in self.children:
            result += child.nodes_to_execute()
        return result


class AssertStmt(KeywordStatement):
    __slots__ = ()

    def assertion(self):
        return self.children[1]


class GlobalStmt(KeywordStatement):
    __slots__ = ()

    def get_defined_names(self):
        return []

    def get_global_names(self):
        return self.children[1::2]

    def nodes_to_execute(self, last_added=False):
        """
        The global keyword allows to define any name. Even if it doesn't
        exist.
        """
        return []


class ReturnStmt(KeywordStatement):
    __slots__ = ()


class YieldExpr(PythonBaseNode):
    __slots__ = ()

    @property
    def type(self):
        return 'yield_expr'

    def nodes_to_execute(self, last_added=False):
        if len(self.children) > 1:
            return self.children[1].nodes_to_execute()
        else:
            return []


def _defined_names(current):
    """
    A helper function to find the defined names in statements, for loops and
    list comprehensions.
    """
    names = []
    if current.type in ('testlist_star_expr', 'testlist_comp', 'exprlist'):
        for child in current.children[::2]:
            names += _defined_names(child)
    elif current.type in ('atom', 'star_expr'):
        names += _defined_names(current.children[1])
    elif current.type in ('power', 'atom_expr'):
        if current.children[-2] != '**':  # Just if there's no operation
            trailer = current.children[-1]
            if trailer.children[0] == '.':
                names.append(trailer.children[1])
    else:
        names.append(current)
    return names


class ExprStmt(PythonBaseNode, DocstringMixin):
    type = 'expr_stmt'
    __slots__ = ()

    def get_defined_names(self):
        names = []
        if self.children[1].type == 'annassign':
            names = _defined_names(self.children[0])
        return list(chain.from_iterable(
            _defined_names(self.children[i])
            for i in range(0, len(self.children) - 2, 2)
            if '=' in self.children[i + 1].value)
        ) + names

    def get_rhs(self):
        """Returns the right-hand-side of the equals."""
        return self.children[-1]

    def first_operation(self):
        """
        Returns `+=`, `=`, etc or None if there is no operation.
        """
        try:
            return self.children[1]
        except IndexError:
            return None

    def nodes_to_execute(self, last_added=False):
        # I think evaluating the statement (and possibly returned arrays),
        # should be enough for static analysis.
        result = [self]
        for child in self.children:
            result += child.nodes_to_execute(last_added=True)
        return result


class Param(PythonBaseNode):
    """
    It's a helper class that makes business logic with params much easier. The
    Python grammar defines no ``param`` node. It defines it in a different way
    that is not really suited to working with parameters.
    """
    type = 'param'

    def __init__(self, children, parent):
        super(Param, self).__init__(children)
        self.parent = parent
        for child in children:
            child.parent = self

    @property
    def stars(self):
        first = self.children[0]
        if first in ('*', '**'):
            return len(first.value)
        return 0

    @property
    def default(self):
        try:
            return self.children[int(self.children[0] in ('*', '**')) + 2]
        except IndexError:
            return None

    def annotation(self):
        tfpdef = self._tfpdef()
        if tfpdef.type == 'tfpdef':
            assert tfpdef.children[1] == ":"
            assert len(tfpdef.children) == 3
            annotation = tfpdef.children[2]
            return annotation
        else:
            return None

    def _tfpdef(self):
        """
        tfpdef: see grammar.txt.
        """
        offset = int(self.children[0] in ('*', '**'))
        return self.children[offset]

    @property
    def name(self):
        if self._tfpdef().type == 'tfpdef':
            return self._tfpdef().children[0]
        else:
            return self._tfpdef()

    @property
    def position_nr(self):
        index = self.parent.children.index(self)
        try:
            keyword_only_index = self.parent.children.index('*')
            if index > keyword_only_index:
                # Skip the ` *, `
                index -= 2
        except ValueError:
            pass
        return index - 1

    def get_parent_function(self):
        return search_ancestor(self, ('funcdef', 'lambda'))

    def __repr__(self):
        default = '' if self.default is None else '=%s' % self.default.get_code()
        return '<%s: %s>' % (type(self).__name__, str(self._tfpdef()) + default)

    def get_description(self):
        children = self.children
        if children[-1] == ',':
            children = children[:-1]
        return self._get_code_for_children(children, False, False)


class CompFor(PythonBaseNode):
    type = 'comp_for'
    __slots__ = ()

    def get_comp_fors(self):
        yield self
        last = self.children[-1]
        while True:
            if isinstance(last, CompFor):
                yield last
            elif not last.type == 'comp_if':
                break
            last = last.children[-1]

    def is_scope(self):
        return True

    def get_defined_names(self):
        return _defined_names(self.children[1])

    def nodes_to_execute(self, last_added=False):
        last = self.children[-1]
        if last.type == 'comp_if':
            for node in last.children[-1].nodes_to_execute():
                yield node
            last = self.children[-2]
        elif last.type == 'comp_for':
            for node in last.nodes_to_execute():
                yield node
            last = self.children[-2]
        for node in last.nodes_to_execute():
            yield node
