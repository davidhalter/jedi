from jedi.parser.parser import Parser, ParserWithRecovery, ParseError
from jedi.parser.pgen2.pgen import generate_grammar


def parse(grammar, code):
    raise NotImplementedError
    Parser(grammar, code)
