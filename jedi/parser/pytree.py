# Copyright 2006 Google, Inc. All Rights Reserved.
# Licensed to PSF under a Contributor Agreement.

"""
Python parse tree definitions.

This is a very concrete parse tree; we need to keep every token and
even the comments and whitespace between tokens.

There's also a pattern matching implementation here.
"""

__author__ = "Guido van Rossum <guido@python.org>"

import os

from . import pgen2
from . import tokenize

_type_reprs = {}


# The grammar file
_GRAMMAR_FILE = os.path.join(os.path.dirname(__file__), "grammar3.4.txt")


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
try:
    del python_grammar_no_print_statement.keywords["print"]
except KeyError:
    pass  # Doesn't exist in the Python 3 grammar.


def type_repr(type_num):
    global _type_reprs
    if not _type_reprs:
        # printing tokens is possible but not as useful
        # from .pgen2 import token // token.__dict__.items():
        for name, val in python_symbols.__dict__.items():
            if type(val) == int:
                _type_reprs[val] = name
    return _type_reprs.setdefault(type_num, type_num)


def convert(grammar, raw_node):
    """
    Convert raw node information to a Node or Leaf instance.

    This is passed to the parser driver which calls it whenever a reduction of a
    grammar rule produces a new complete node, so that the tree is build
    strictly bottom-up.
    """

    from jedi.parser import representation as pr
    _ast_mapping = {
        'expr_stmt': pr.ExprStmt,
        'classdef': pr.Class,
        'funcdef': pr.Function,
        'file_input': pr.SubModule,
        'import_name': pr.Import,
        'import_from': pr.Import,
        'break_stmt': pr.KeywordStatement,
        'continue_stmt': pr.KeywordStatement,
        'return_stmt': pr.ReturnStmt,
        'raise_stmt': pr.KeywordStatement,
        'yield_stmt': pr.ReturnStmt,
        'del_stmt': pr.KeywordStatement,
        'pass_stmt': pr.KeywordStatement,
        'global_stmt': pr.GlobalStmt,
        'nonlocal_stmt': pr.KeywordStatement,
        'assert_stmt': pr.KeywordStatement,
    }

    ast_mapping = dict((getattr(python_symbols, k), v) for k, v in _ast_mapping.items())


    #import pdb; pdb.set_trace()
    type, value, context, children = raw_node
    if type in grammar.number2symbol:
        # If there's exactly one child, return that child instead of
        # creating a new node.
        # We still create expr_stmt though, because a lot of Jedi depends on
        # its logic.
        if len(children) == 1 and type != python_symbols.expr_stmt:
            return children[0]
        print(raw_node, type_repr(type))
        #import pdb; pdb.set_trace()
        try:
            return ast_mapping[type](children)
        except KeyError:
            return pr.Node(type, children)
    else:
        print('leaf', raw_node, type_repr(type))
        prefix, start_pos = context
        if type == tokenize.NAME:
            if value in grammar.keywords:
                return pr.Keyword(value, start_pos, prefix)
            else:
                return pr.Name(value, start_pos, prefix)
        elif type in (tokenize.STRING, tokenize.NUMBER):
            return pr.Literal(value, start_pos, prefix)
        elif type in (tokenize.NEWLINE, tokenize.ENDMARKER):
            return pr.Whitespace(value, start_pos, prefix)
        else:
            return pr.Operator(value, start_pos, prefix)
