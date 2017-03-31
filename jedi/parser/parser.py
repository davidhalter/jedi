"""
The ``Parser`` tries to convert the available Python code in an easy to read
format, something like an abstract syntax tree. The classes who represent this
tree, are sitting in the :mod:`jedi.parser.tree` module.

The Python module ``tokenize`` is a very important part in the ``Parser``,
because it splits the code into different words (tokens).  Sometimes it looks a
bit messy. Sorry for that! You might ask now: "Why didn't you use the ``ast``
module for this? Well, ``ast`` does a very good job understanding proper Python
code, but fails to work as soon as there's a single line of broken code.

There's one important optimization that needs to be known: Statements are not
being parsed completely. ``Statement`` is just a representation of the tokens
within the statement. This lowers memory usage and cpu time and reduces the
complexity of the ``Parser`` (there's another parser sitting inside
``Statement``, which produces ``Array`` and ``Call``).
"""
from jedi.parser import tree
from jedi.parser.pgen2.parse import PgenParser


class ParserSyntaxError(Exception):
    """
    Contains error information about the parser tree.

    May be raised as an exception.
    """
    def __init__(self, message, position):
        self.message = message
        self.position = position


class BaseParser(object):
    node_map = {}
    default_node = tree.Node

    leaf_map = {
    }
    default_leaf = tree.Leaf

    def __init__(self, grammar, start_symbol='file_input', error_recovery=False):
        self._grammar = grammar
        self._start_symbol = start_symbol
        self._error_recovery = error_recovery

    def parse(self, tokens):
        start_number = self._grammar.symbol2number[self._start_symbol]
        self.pgen_parser = PgenParser(
            self._grammar, self.convert_node, self.convert_leaf,
            self.error_recovery, start_number
        )

        node = self.pgen_parser.parse(tokens)
        # The stack is empty now, we don't need it anymore.
        del self.pgen_parser
        return node

    def error_recovery(self, grammar, stack, arcs, typ, value, start_pos, prefix,
                       add_token_callback):
        if self._error_recovery:
            raise NotImplementedError("Error Recovery is not implemented")
        else:
            raise ParserSyntaxError('SyntaxError: invalid syntax', start_pos)

    def convert_node(self, grammar, type_, children):
        # TODO REMOVE symbol, we don't want type here.
        symbol = grammar.number2symbol[type_]
        try:
            return self.node_map[symbol](children)
        except KeyError:
            return self.default_node(symbol, children)

    def convert_leaf(self, grammar, type_, value, prefix, start_pos):
        try:
            return self.leaf_map[type_](value, start_pos, prefix)
        except KeyError:
            return self.default_leaf(value, start_pos, prefix)
