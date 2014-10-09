import logging

from jedi.parser import pytree
from jedi.parser.pgen2 import Driver


def test_basic_parsing():
    def compare(string):
        """Generates the AST object and then regenerates the code."""
        assert d.parse_string(string).get_code() == string

    #if self.options["print_function"]:
    #    python_grammar = pygram.python_grammar_no_print_statement
    #else:
    # When this is True, the refactor*() methods will call write_file() for
    # files processed even if they were not changed during refactoring. If
    # and only if the refactor method's write parameter was True.
    logger = logging.getLogger("RefactoringTool")
    d = Driver(pytree.python_grammar, convert=pytree.convert, logger=logger)

    compare('\na #pass\n')
    compare('wblabla* 1\t\n')
    compare('def x(a, b:3): pass\n')
    compare('assert foo\n')
