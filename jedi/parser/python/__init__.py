"""
Parsers for Python
"""
import os

from jedi._compatibility import FileNotFoundError
from jedi.parser.pgen2.pgen import generate_grammar
from jedi.parser.python.parser import Parser, ParserWithRecovery
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


def parse(code, grammar=None, error_recovery=True, start_symbol='file_input'):
    """
    If you want to parse a Python file you want to start here, most likely.

    If you need finer grained control over the parsed instance, there will be
    other ways to access it.

    :param code: A unicode string that contains Python code.
    :param grammar: A Python grammar file, created with load_grammar.
    :param error_recovery: If enabled, any code will be returned. If it is
        invalid, it will be returned as an error node. If disabled, you will
        get a ParseError when encountering syntax errors in your code.
    :param start_symbol: The grammar symbol that you want to parse. Only
        allowed to be used when error_recovery is disabled.

    :return: A syntax tree node. Typically the module.
    """
    if start_symbol != 'file_input' and error_recovery:
        raise Exception(
            'The start_symbol is only allowed when error recovery is disabled.')

    added_newline = not code.endswith('\n')
    if added_newline:
        code += '\n'

    if grammar is None:
        grammar = load_grammar()

    tokens = source_tokens(code, use_exact_op_types=True)
    kwargs = {}
    if error_recovery:
        parser = ParserWithRecovery
    else:
        kwargs = dict(start_symbol=start_symbol)
        parser = Parser
    p = parser(grammar, code, start_parsing=False, **kwargs)
    module = p.parse(tokens=tokens)
    if added_newline:
        p._remove_last_newline()

    return module
