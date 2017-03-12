import os

from jedi._compatibility import FileNotFoundError
from jedi.parser.pgen2.pgen import generate_grammar
from jedi.parser.parser import Parser, ParserWithRecovery
from jedi.parser.tokenize import source_tokens


_loaded_grammars = {}


def load_grammar(version='3.6'):
    # For now we only support two different Python syntax versions: The latest
    # Python 3 and Python 2. This may change.
    if version in ('3.2', '3.3'):
        version = '3.4'
    elif version == '2.6':
        version = '2.7'

    file = 'grammar' + version + '.txt'

    global _loaded_grammars
    path = os.path.join(os.path.dirname(__file__), file)
    try:
        return _loaded_grammars[path]
    except KeyError:
        try:
            return _loaded_grammars.setdefault(path, generate_grammar(path))
        except FileNotFoundError:
            # Just load the default if the file does not exist.
            return load_grammar()


def parse(source, grammar=None, error_recovery=False):
    if grammar is None:
        grammar = load_grammar()

    tokens = source_tokens(source)
    if error_recovery:
        parser = ParserWithRecovery
    else:
        parser = Parser
    parser(grammar, tokens)
