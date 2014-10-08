# Copyright 2006 Google, Inc. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

"""
Python parse tree definitions.

This is a very concrete parse tree; we need to keep every token and
even the comments and whitespace between tokens.

There's also a pattern matching implementation here.
"""

__author__ = "Guido van Rossum <guido@python.org>"

import sys
import os

from . import pgen2

HUGE = 0x7FFFFFFF  # maximum repeat count, default max

_type_reprs = {}


# The grammar file
_GRAMMAR_FILE = os.path.join(os.path.dirname(__file__), "grammar.txt")


class Symbols(object):

    def __init__(self, grammar):
        """Initializer.

        Creates an attribute for each grammar symbol (nonterminal),
        whose value is the symbol's type (an int >= 256).
        """
        for name, symbol in grammar.symbol2number.items():
            setattr(self, name, symbol)


python_grammar = pgen2.load_grammar(_GRAMMAR_FILE)

python_symbols = Symbols(python_grammar)

python_grammar_no_print_statement = python_grammar.copy()
del python_grammar_no_print_statement.keywords["print"]


def type_repr(type_num):
    global _type_reprs
    if not _type_reprs:
        # printing tokens is possible but not as useful
        # from .pgen2 import token // token.__dict__.items():
        for name, val in python_symbols.__dict__.items():
            if type(val) == int:
                _type_reprs[val] = name
    return _type_reprs.setdefault(type_num, type_num)


class Base(object):

    """
    Abstract base class for Node and Leaf.

    This provides some default functionality and boilerplate using the
    template pattern.

    A node may be a subnode of at most one parent.
    """

    # Default values for instance variables
    type = None    # int: token number (< 256) or symbol number (>= 256)
    parent = None  # Parent node pointer, or None
    children = ()  # Tuple of subnodes
    was_changed = False
    was_checked = False

    def __new__(cls, *args, **kwds):
        """Constructor that prevents Base from being instantiated."""
        assert cls is not Base, "Cannot instantiate Base"
        return object.__new__(cls)

    def __eq__(self, other):
        """
        Compare two nodes for equality.

        This calls the method _eq().
        """
        if self.__class__ is not other.__class__:
            return NotImplemented
        return self._eq(other)

    __hash__ = None  # For Py3 compatibility.

    def __ne__(self, other):
        """
        Compare two nodes for inequality.

        This calls the method _eq().
        """
        if self.__class__ is not other.__class__:
            return NotImplemented
        return not self._eq(other)

    def _eq(self, other):
        """
        Compare two nodes for equality.

        This is called by __eq__ and __ne__.  It is only called if the two nodes
        have the same type.  This must be implemented by the concrete subclass.
        Nodes should be considered equal if they have the same structure,
        ignoring the prefix string and other context information.
        """
        raise NotImplementedError

    def clone(self):
        """
        Return a cloned (deep) copy of self.

        This must be implemented by the concrete subclass.
        """
        raise NotImplementedError

    def post_order(self):
        """
        Return a post-order iterator for the tree.

        This must be implemented by the concrete subclass.
        """
        raise NotImplementedError

    def pre_order(self):
        """
        Return a pre-order iterator for the tree.

        This must be implemented by the concrete subclass.
        """
        raise NotImplementedError

    def replace(self, new):
        """Replace this node with a new one in the parent."""
        assert self.parent is not None, str(self)
        assert new is not None
        if not isinstance(new, list):
            new = [new]
        l_children = []
        found = False
        for ch in self.parent.children:
            if ch is self:
                assert not found, (self.parent.children, self, new)
                if new is not None:
                    l_children.extend(new)
                found = True
            else:
                l_children.append(ch)
        assert found, (self.children, self, new)
        self.parent.changed()
        self.parent.children = l_children
        for x in new:
            x.parent = self.parent
        self.parent = None

    def get_lineno(self):
        """Return the line number which generated the invocant node."""
        node = self
        while not isinstance(node, Leaf):
            if not node.children:
                return
            node = node.children[0]
        return node.lineno

    def changed(self):
        if self.parent:
            self.parent.changed()
        self.was_changed = True

    def remove(self):
        """
        Remove the node from the tree. Returns the position of the node in its
        parent's children before it was removed.
        """
        if self.parent:
            for i, node in enumerate(self.parent.children):
                if node is self:
                    self.parent.changed()
                    del self.parent.children[i]
                    self.parent = None
                    return i

    @property
    def next_sibling(self):
        """
        The node immediately following the invocant in their parent's children
        list. If the invocant does not have a next sibling, it is None
        """
        if self.parent is None:
            return None

        # Can't use index(); we need to test by identity
        for i, child in enumerate(self.parent.children):
            if child is self:
                try:
                    return self.parent.children[i + 1]
                except IndexError:
                    return None

    @property
    def prev_sibling(self):
        """
        The node immediately preceding the invocant in their parent's children
        list. If the invocant does not have a previous sibling, it is None.
        """
        if self.parent is None:
            return None

        # Can't use index(); we need to test by identity
        for i, child in enumerate(self.parent.children):
            if child is self:
                if i == 0:
                    return None
                return self.parent.children[i - 1]

    def leaves(self):
        for child in self.children:
            for leave in child.leaves():
                yield leave

    def depth(self):
        if self.parent is None:
            return 0
        return 1 + self.parent.depth()

    def get_suffix(self):
        """
        Return the string immediately following the invocant node. This is
        effectively equivalent to node.next_sibling.prefix
        """
        next_sib = self.next_sibling
        if next_sib is None:
            return ""
        return next_sib.prefix

    if sys.version_info < (3, 0):
        def __str__(self):
            return str(self).encode("ascii")


class Node(Base):
    """Concrete implementation for interior nodes."""

    def __init__(self, type, children,
                 context=None,
                 prefix=None,
                 fixers_applied=None):
        """
        Initializer.

        Takes a type constant (a symbol number >= 256), a sequence of
        child nodes, and an optional context keyword argument.

        As a side effect, the parent pointers of the children are updated.
        """
        assert type >= 256, type
        self.type = type
        self.children = list(children)
        for ch in self.children:
            assert ch.parent is None, repr(ch)
            ch.parent = self
        if prefix is not None:
            self.prefix = prefix
        if fixers_applied:
            self.fixers_applied = fixers_applied[:]
        else:
            self.fixers_applied = None

    def __repr__(self):
        """Return a canonical string representation."""
        return "%s(%s, %r)" % (self.__class__.__name__,
                               type_repr(self.type),
                               self.children)

    def __unicode__(self):
        """
        Return a pretty string representation.

        This reproduces the input source exactly.
        """
        return "".join(map(str, self.children))

    if sys.version_info > (3, 0):
        __str__ = __unicode__

    def _eq(self, other):
        """Compare two nodes for equality."""
        return (self.type, self.children) == (other.type, other.children)

    def clone(self):
        """Return a cloned (deep) copy of self."""
        return Node(self.type, [ch.clone() for ch in self.children],
                    fixers_applied=self.fixers_applied)

    def post_order(self):
        """Return a post-order iterator for the tree."""
        for child in self.children:
            for el in child.post_order():
                yield el
        yield self

    def pre_order(self):
        """Return a pre-order iterator for the tree."""
        yield self
        for child in self.children:
            for el in child.post_order():
                yield el

    def _prefix_getter(self):
        """
        The whitespace and comments preceding this node in the input.
        """
        if not self.children:
            return ""
        return self.children[0].prefix

    def _prefix_setter(self, prefix):
        if self.children:
            self.children[0].prefix = prefix

    prefix = property(_prefix_getter, _prefix_setter)

    def set_child(self, i, child):
        """
        Equivalent to 'node.children[i] = child'. This method also sets the
        child's parent attribute appropriately.
        """
        child.parent = self
        self.children[i].parent = None
        self.children[i] = child
        self.changed()

    def insert_child(self, i, child):
        """
        Equivalent to 'node.children.insert(i, child)'. This method also sets
        the child's parent attribute appropriately.
        """
        child.parent = self
        self.children.insert(i, child)
        self.changed()

    def append_child(self, child):
        """
        Equivalent to 'node.children.append(child)'. This method also sets the
        child's parent attribute appropriately.
        """
        child.parent = self
        self.children.append(child)
        self.changed()


class Leaf(Base):

    """Concrete implementation for leaf nodes."""

    # Default values for instance variables
    _prefix = ""  # Whitespace and comments preceding this token in the input
    lineno = 0    # Line where this token starts in the input
    column = 0    # Column where this token tarts in the input

    def __init__(self, type, value,
                 context=None,
                 prefix=None,
                 fixers_applied=[]):
        """
        Initializer.

        Takes a type constant (a token number < 256), a string value, and an
        optional context keyword argument.
        """
        assert 0 <= type < 256, type
        if context is not None:
            self._prefix, (self.lineno, self.column) = context
        self.type = type
        self.value = value
        if prefix is not None:
            self._prefix = prefix
        self.fixers_applied = fixers_applied[:]

    def __repr__(self):
        """Return a canonical string representation."""
        return "%s(%r, %r)" % (self.__class__.__name__,
                               self.type,
                               self.value)

    def __unicode__(self):
        """
        Return a pretty string representation.

        This reproduces the input source exactly.
        """
        return self.prefix + str(self.value)

    if sys.version_info > (3, 0):
        __str__ = __unicode__

    def _eq(self, other):
        """Compare two nodes for equality."""
        return (self.type, self.value) == (other.type, other.value)

    def clone(self):
        """Return a cloned (deep) copy of self."""
        return Leaf(self.type, self.value,
                    (self.prefix, (self.lineno, self.column)),
                    fixers_applied=self.fixers_applied)

    def leaves(self):
        yield self

    def post_order(self):
        """Return a post-order iterator for the tree."""
        yield self

    def pre_order(self):
        """Return a pre-order iterator for the tree."""
        yield self

    def _prefix_getter(self):
        """
        The whitespace and comments preceding this token in the input.
        """
        return self._prefix

    def _prefix_setter(self, prefix):
        self.changed()
        self._prefix = prefix

    prefix = property(_prefix_getter, _prefix_setter)


def convert(gr, raw_node):
    """
    Convert raw node information to a Node or Leaf instance.

    This is passed to the parser driver which calls it whenever a reduction of a
    grammar rule produces a new complete node, so that the tree is build
    strictly bottom-up.
    """
    #import pdb; pdb.set_trace()
    print(raw_node)
    type, value, context, children = raw_node
    if children or type in gr.number2symbol:
        # If there's exactly one child, return that child instead of
        # creating a new node.
        if len(children) == 1:
            return children[0]
        return Node(type, children, context=context)
    else:
        return Leaf(type, value, context=context)
