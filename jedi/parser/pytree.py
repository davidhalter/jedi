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

    def leaves(self):
        for child in self.children:
            for leave in child.leaves():
                yield leave

    if sys.version_info < (3, 0):
        def __str__(self):
            return str(self).encode("ascii")


class Node(Base):
    """Concrete implementation for interior nodes."""

    def __init__(self, type, children,
                 context=None,
                 prefix=None):
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

    @property
    def prefix(self):
        """
        The whitespace and comments preceding this node in the input.
        """
        if not self.children:
            return ""
        return self.children[0].prefix

    @prefix.setter
    def prefix(self, prefix):
        if self.children:
            self.children[0].prefix = prefix
        else:
            raise NotImplementedError

    def append_child(self, child):
        """
        Equivalent to 'node.children.append(child)'. This method also sets the
        child's parent attribute appropriately.
        """
        child.parent = self
        self.children.append(child)


class Leaf(Base):

    """Concrete implementation for leaf nodes."""

    # Default values for instance variables
    _prefix = ""  # Whitespace and comments preceding this token in the input
    lineno = 0    # Line where this token starts in the input
    column = 0    # Column where this token tarts in the input

    def __init__(self, type, value, context=None, prefix=None):
        """
        Initializer.

        Takes a type constant (a token number < 256), a string value, and an
        optional context keyword argument.
        """
        assert 0 <= type < 256, type
        if context is not None:
            self.prefix, (self.lineno, self.column) = context
        if prefix is not None:
            # The whitespace and comments preceding this token in the input.
            self.prefix = prefix
        self.type = type
        self.value = value

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

    def leaves(self):
        yield self


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
