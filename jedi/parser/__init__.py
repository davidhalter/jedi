from jedi.parser.parser import ParserSyntaxError
from jedi.parser.python.parser import Parser
from jedi.parser.pgen2.pgen import generate_grammar
from jedi.parser import python


def parse(grammar, code):
    raise NotImplementedError
    Parser(grammar, code)
