import os

from jedi._compatibility import FileNotFoundError
from jedi.parser.pgen2.pgen import generate_grammar
from jedi.parser.parser import Parser, ParserWithRecovery
from jedi.parser.tokenize import source_tokens


_loaded_grammars = {}


def load_grammar(version=None):
    """
    Loads a Python grammar. The default version is always the latest.

    If you need support for a specific version, please use e.g.
    `version='3.3'`.
    """
    if version is None:
        version = '3.6'

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
            with open(path) as f:
                bnf_text = f.read()
            grammar = generate_grammar(bnf_text)
            return _loaded_grammars.setdefault(path, grammar)
        except FileNotFoundError:
            # Just load the default if the file does not exist.
            return load_grammar()


def parse(code, grammar=None, error_recovery=True):
    added_newline = not code.endswith('\n')
    if added_newline:
        code += '\n'

    if grammar is None:
        grammar = load_grammar()

    tokens = source_tokens(code, use_exact_op_types=True)
    if error_recovery:
        parser = ParserWithRecovery
    else:
        parser = Parser
    p = parser(grammar, code, tokens=tokens)
    if added_newline:
        p.remove_last_newline()
    return p.get_root_node()
