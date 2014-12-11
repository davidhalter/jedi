from jedi.parser import Parser, load_grammar


def test_basic_parsing():
    def compare(string):
        """Generates the AST object and then regenerates the code."""
        assert Parser(load_grammar(), string).module.get_code() == string

    compare('\na #pass\n')
    compare('wblabla* 1\t\n')
    compare('def x(a, b:3): pass\n')
    compare('assert foo\n')
