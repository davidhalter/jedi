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

class ParserSyntaxError(Exception):
    """
    Contains error information about the parser tree.

    May be raised as an exception.
    """
    def __init__(self, message, position):
        self.message = message
        self.position = position


class Parser(object):
    AST_MAPPING = {}

    def __init__(self, grammar, tokens, start_symbol='file_input'):
        self._grammar = grammar
        self._start_symbol = start_symbol
        self._parsed = None

