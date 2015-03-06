from jedi._compatibility import u
from jedi.parser import Parser, load_grammar


def test_basic_parsing():
    def compare(string):
        """Generates the AST object and then regenerates the code."""
        assert Parser(load_grammar(), string).module.get_code() == string

    compare(u('\na #pass\n'))
    compare(u('wblabla* 1\t\n'))
    compare(u('def x(a, b:3): pass\n'))
    compare(u('assert foo\n'))
