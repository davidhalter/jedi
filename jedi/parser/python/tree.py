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
:attr:`iter_imports <Scope.iter_imports>`:

>>> list(module.iter_imports())
[<ImportName: import os@1,0>]
"""

from jedi import cache
from jedi._compatibility import utf8_repr, unicode
from jedi.parser.tree import Node, BaseNode, Leaf, ErrorNode, ErrorLeaf, \
    search_ancestor


class DocstringMixin(object):
    __slots__ = ()

    def get_doc_node(self):
        """
        Returns the string leaf of a docstring. e.g. ``r'''foo'''``.
        """
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
                return None
            node = c[index - 1]

        if node.type == 'simple_stmt':
            node = node.children[0]
        if node.type == 'string':
            return node
        return None


class PythonMixin(object):
    """
    Some Python specific utitilies.
    """
    __slots__ = ()

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

    def get_name_of_position(self, position):
        for c in self.children:
            if isinstance(c, Leaf):
                if c.type == 'name' and c.start_pos <= position <= c.end_pos:
                    return c
            else:
                result = c.get_name_of_position(position)
                if result is not None:
                    return result
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

    def __repr__(self):
        return "<%s: %s@%s,%s>" % (type(self).__name__, self.value,
                                   self.line, self.indent)

    @cache.memoize_method
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


class Literal(PythonLeaf):
    __slots__ = ()


class Number(Literal):
    type = 'number'
    __slots__ = ()


class String(Literal):
    type = 'string'
    __slots__ = ()


class _StringComparisonMixin(object):
    def __eq__(self, other):
        """
        Make comparisons with strings easy.
        Improves the readability of the parser.
        """
        if isinstance(other, (str, unicode)):
            return self.value == other

        return self is other

    def __ne__(self, other):
        """Python 2 compatibility."""
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.value)


class Operator(_LeafWithoutNewlines, _StringComparisonMixin):
    type = 'operator'
    __slots__ = ()


class Keyword(_LeafWithoutNewlines, _StringComparisonMixin):
    type = 'keyword'
    __slots__ = ()


class Scope(PythonBaseNode, DocstringMixin):
    """
    Super class for the parser tree, which represents the state of a python
    text file.
    A Scope is either a function, class or lambda.
    """
    __slots__ = ()

    def __init__(self, children):
        super(Scope, self).__init__(children)

    def iter_funcdefs(self):
        """
        Returns a generator of `funcdef` nodes.
        """
        return self._search_in_scope('funcdef')

    def iter_classdefs(self):
        """
        Returns a generator of `classdef` nodes.
        """
        return self._search_in_scope('classdef')

    def iter_imports(self):
        """
        Returns a generator of `import_name` and `import_from` nodes.
        """
        return self._search_in_scope('import_name', 'import_from')

    def _search_in_scope(self, *names):
        def scan(children):
            for element in children:
                if element.type in names:
                    yield element
                if element.type in ('suite', 'simple_stmt', 'decorated') \
                        or isinstance(element, Flow):
                    for e in scan(element.children):
                        yield e

        return scan(self.children)

    def get_suite(self):
        """
        Returns the part that is executed by the function.
        """
        return self.children[-1]

    def __repr__(self):
        try:
            name = self.name.value
        except AttributeError:
            name = ''

        return "<%s: %s@%s-%s>" % (type(self).__name__, name,
                                   self.start_pos[0], self.end_pos[0])


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

    def iter_future_import_names(self):
        """
        :return list of str: A list of future import names.
        """
        # TODO this is a strange scan and not fully correct. I think Python's
        # parser does it in a different way and scans for the first
        # statement/import with a tokenizer (to check for syntax changes like
        # the future print statement).
        for imp in self.iter_imports():
            if imp.type == 'import_from' and imp.level == 0:
                for path in imp.get_paths():
                    names = [name.value for name in path]
                    if len(names) == 2 and names[0] == '__future__':
                        yield names[1]

    def has_explicit_absolute_import(self):
        """
        Checks if imports in this module are explicitly absolute, i.e. there
        is a ``__future__`` import.
        :return bool:
        """
        for name in self.iter_future_import_names():
            if name == 'absolute_import':
                return True
        return False

    def get_used_names(self):
        """
        Returns all the `Name` leafs that exist in this module. Tihs includes
        both definitions and references of names.
        """
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


class ClassOrFunc(Scope):
    __slots__ = ()

    @property
    def name(self):
        """
        Returns the `Name` leaf that defines the function or class name.
        """
        return self.children[1]

    def get_decorators(self):
        """
        :return list of Decorator:
        """
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
        """
        Returns the `arglist` node that defines the super classes. It returns
        None if there are no arguments.
        """
        if self.children[2] != '(':  # Has no parentheses
            return None
        else:
            if self.children[3] == ')':  # Empty parentheses
                return None
            else:
                return self.children[3]


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

    Children::

        0. <Keyword: def>
        1. <Name>
        2. parameter list (including open-paren and close-paren <Operator>s)
        3. or 5. <Operator: :>
        4. or 6. Node() representing function body
        3. -> (if annotation is also present)
        4. annotation (if present)
    """
    type = 'funcdef'

    def __init__(self, children):
        super(Function, self).__init__(children)
        parameters = self.children[2]  # After `def foo`
        parameters.children[1:-1] = _create_params(parameters, parameters.children[1:-1])

    def _get_param_nodes(self):
        return self.children[2].children

    @property
    def params(self):
        """
        Returns a list of `Param()`.
        """
        return [p for p in self._get_param_nodes() if p.type == 'param']

    @property
    def name(self):
        return self.children[1]  # First token after `def`

    def iter_yield_exprs(self):
        """
        Returns a generator of `yield_expr`.
        """
        # TODO This is incorrect, yields are also possible in a statement.
        return self._search_in_scope('yield_expr')

    def iter_return_stmts(self):
        """
        Returns a generator of `return_stmt`.
        """
        return self._search_in_scope('return_stmt')

    def is_generator(self):
        """
        :return bool: Checks if a function is a generator or not.
        """
        return next(self.iter_yield_exprs(), None) is not None

    @property
    def annotation(self):
        """
        Returns the test node after `->` or `None` if there is no annotation.
        """
        try:
            if self.children[3] == "->":
                return self.children[4]
            assert self.children[3] == ":"
            return None
        except IndexError:
            return None

class Lambda(Function):
    """
    Lambdas are basically trimmed functions, so give it the same interface.

    Children::

         0. <Keyword: lambda>
         *. <Param x> for each argument x
        -2. <Operator: :>
        -1. Node() representing body
    """
    type = 'lambdef'
    __slots__ = ()

    def __init__(self, children):
        # We don't want to call the Function constructor, call its parent.
        super(Function, self).__init__(children)
        # Everything between `lambda` and the `:` operator is a parameter.
        self.children[1:-2] = _create_params(self, self.children[1:-2])

    @property
    def name(self):
        """
        Raises an AttributeError. Lambdas don't have a defined name.
        """
        raise AttributeError("lambda is not named.")

    def _get_param_nodes(self):
        return self.children[1:-2]

    @property
    def annotation(self):
        """
        Returns `None`, lambdas don't have annotations.
        """
        return None

    def __repr__(self):
        return "<%s@%s>" % (self.__class__.__name__, self.start_pos)


class Flow(PythonBaseNode):
    __slots__ = ()


class IfStmt(Flow):
    type = 'if_stmt'
    __slots__ = ()

    def get_test_nodes(self):
        """
        E.g. returns all the `test` nodes that are named as x, below:

            if x:
                pass
            elif x:
                pass
        """
        for i, c in enumerate(self.children):
            if c in ('elif', 'if'):
                yield self.children[i + 1]

    def get_corresponding_test_node(self, node):
        """
        Searches for the branch in which the node is and returns the
        corresponding test node (see function above). However if the node is in
        the test node itself and not in the suite return None.
        """
        start_pos = node.start_pos
        for check_node in reversed(list(self.get_test_nodes())):
            if check_node.start_pos < start_pos:
                if start_pos < check_node.end_pos:
                    return None
                    # In this case the node is within the check_node itself,
                    # not in the suite
                else:
                    return check_node

    def is_node_after_else(self, node):
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

    def get_testlist(self):
        """
        Returns the input node ``y`` from: ``for x in y:``.
        """
        return self.children[3]


class TryStmt(Flow):
    type = 'try_stmt'
    __slots__ = ()

    def get_except_clause_tests(self):
        """
        Returns the ``test`` nodes found in ``except_clause`` nodes.
        Returns ``[None]`` for except clauses without an exception given.
        """
        for node in self.children:
            # TODO this is not correct. We're not returning an except clause.
            if node.type == 'except_clause':
                yield node.children[1]
            elif node == 'except':
                yield None


class WithStmt(Flow):
    type = 'with_stmt'
    __slots__ = ()

    def get_defined_names(self):
        """
        Returns the a list of `Name` that the with statement defines. The
        defined names are set after `as`.
        """
        names = []
        for with_item in self.children[1:-2:2]:
            # Check with items for 'as' names.
            if with_item.type == 'with_item':
                names += _defined_names(with_item.children[2])
        return names

    def get_context_manager_from_name(self, name):
        # TODO Replace context_manager with test?
        node = name.parent
        if node.type != 'with_item':
            raise ValueError('The name is not actually part of a with statement.')
        return node.children[0]


class Import(PythonBaseNode):
    __slots__ = ()

    def get_path_for_name(self, name):
        """
        The path is the list of names that leads to the searched name.

        :return list of Name:
        """
        try:
            # The name may be an alias. If it is, just map it back to the name.
            name = self._aliases()[name]
        except KeyError:
            pass

        for path in self.get_paths():
            if name in path:
                return path[:path.index(name) + 1]
        raise ValueError('Name should be defined in the import itself')

    def is_nested(self):
        return False  # By default, sub classes may overwrite this behavior

    def is_star_import(self):
        return self.children[-1] == '*'


class ImportFrom(Import):
    type = 'import_from'
    __slots__ = ()

    def get_defined_names(self):
        """
        Returns the a list of `Name` that the import defines. The
        defined names are set after `import` or in case an alias - `as` - is
        present that name is returned.
        """
        return [alias or name for name, alias in self._as_name_tuples()]

    def _aliases(self):
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

    def get_paths(self):
        """
        The import paths defined in an import statement. Typically an array
        like this: ``[<Name: datetime>, <Name: date>]``.

        :return list of list of Name:
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
        """
        Returns the a list of `Name` that the import defines. The defined names
        is always the first name after `import` or in case an alias - `as` - is
        present that name is returned.
        """
        return [alias or path[0] for path, alias in self._dotted_as_names()]

    @property
    def level(self):
        """The level parameter of ``__import__``."""
        return 0  # Obviously 0 for imports without from.

    def get_paths(self):
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
        return bool([1 for path, alias in self._dotted_as_names()
                    if alias is None and len(path) > 1])

    def _aliases(self):
        """
        :return list of Name: Returns all the alias
        """
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


class AssertStmt(KeywordStatement):
    __slots__ = ()

    @property
    def assertion(self):
        return self.children[1]


class GlobalStmt(KeywordStatement):
    __slots__ = ()

    def get_global_names(self):
        return self.children[1::2]


class ReturnStmt(KeywordStatement):
    __slots__ = ()


class YieldExpr(PythonBaseNode):
    type = 'yield_expr'
    __slots__ = ()


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
        """
        Returns a list of `Name` defined before the `=` sign.
        """
        names = []
        if self.children[1].type == 'annassign':
            names = _defined_names(self.children[0])
        return [
            name
            for i in range(0, len(self.children) - 2, 2)
            if '=' in self.children[i + 1].value
            for name in _defined_names(self.children[i])
        ] + names

    def get_rhs(self):
        """Returns the right-hand-side of the equals."""
        return self.children[-1]

    def yield_operators(self):
        """
        Returns a generator of `+=`, `=`, etc. or None if there is no operation.
        """
        first = self.children[1]
        if first.type == 'annassign':
            if len(first.children) <= 2:
                return  # No operator is available, it's just PEP 484.

            first = first.children[2]
        yield first

        for operator in self.children[3::2]:
            yield operator


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
    def star_count(self):
        """
        Is `0` in case of `foo`, `1` in case of `*foo` or `2` in case of
        `**foo`.
        """
        first = self.children[0]
        if first in ('*', '**'):
            return len(first.value)
        return 0

    @property
    def default(self):
        """
        The default is the test node that appears after the `=`. Is `None` in
        case no default is present.
        """
        try:
            return self.children[int(self.children[0] in ('*', '**')) + 2]
        except IndexError:
            return None

    @property
    def annotation(self):
        """
        The default is the test node that appears after `->`. Is `None` in case
        no annotation is present.
        """
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
        """
        The `Name` leaf of the param.
        """
        if self._tfpdef().type == 'tfpdef':
            return self._tfpdef().children[0]
        else:
            return self._tfpdef()

    @property
    def position_index(self):
        """
        Property for the positional index of a paramter.
        """
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
        """
        Returns the function/lambda of a parameter.
        """
        return search_ancestor(self, 'funcdef', 'lambdef')

    def get_code(self, normalized=False, include_prefix=True, include_comma=True):
        """
        Like all the other get_code functions, but includes the param
        `include_comma`.

        :param include_comma bool: If enabled includes the comma in the string output.
        """
        if include_comma:
            return super(Param, self).get_code(normalized, include_prefix)

        children = self.children
        if children[-1] == ',':
            children = children[:-1]
        return self._get_code_for_children(
            children,
            normalized=False,
            include_prefix=include_prefix
        )

    def __repr__(self):
        default = '' if self.default is None else '=%s' % self.default.get_code()
        return '<%s: %s>' % (type(self).__name__, str(self._tfpdef()) + default)


class CompFor(PythonBaseNode):
    type = 'comp_for'
    __slots__ = ()

    def get_defined_names(self):
        """
        Returns the a list of `Name` that the comprehension defines.
        """
        return _defined_names(self.children[1])
