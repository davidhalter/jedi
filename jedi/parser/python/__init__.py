"""
Parsers for Python
"""
import os

from jedi._compatibility import FileNotFoundError
from jedi.parser.pgen2.pgen import generate_grammar
from jedi.parser.python.parser import Parser, ParserWithRecovery, \
    _remove_last_newline
from jedi.parser.python.diff import DiffParser
from jedi.parser.tokenize import source_tokens
from jedi.parser import utils
from jedi.common import splitlines, source_to_unicode


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


def parse(code=None, path=None, grammar=None, error_recovery=True,
          start_symbol='file_input', cache=False, diff_cache=False):
    """
    If you want to parse a Python file you want to start here, most likely.

    If you need finer grained control over the parsed instance, there will be
    other ways to access it.

    :param code: A unicode string that contains Python code.
    :param path: The path to the file you want to open. Only needed for caching.
    :param grammar: A Python grammar file, created with load_grammar.
    :param error_recovery: If enabled, any code will be returned. If it is
        invalid, it will be returned as an error node. If disabled, you will
        get a ParseError when encountering syntax errors in your code.
    :param start_symbol: The grammar symbol that you want to parse. Only
        allowed to be used when error_recovery is disabled.

    :return: A syntax tree node. Typically the module.
    """
    if code is None and path is None:
        raise TypeError("Please provide either code or a path.")

    if grammar is None:
        grammar = load_grammar()

    if path is not None:
        path = os.path.expanduser(path)

    use_cache = cache and path is not None and not code
    if use_cache:
        # In this case we do actual caching. We just try to load it.
        p = utils.load_parser(grammar, path)
        if p is not None:
            return p.get_root_node()

    if code is None:
        with open(path, 'rb') as f:
            code = source_to_unicode(f.read())

    added_newline = not code.endswith('\n')
    if added_newline:
        code += '\n'

    tokens = source_tokens(code, use_exact_op_types=True)
    kwargs = {}
    if error_recovery:
        parser = ParserWithRecovery
        kwargs = dict()
    else:
        kwargs = dict(start_symbol=start_symbol)
        parser = Parser
    # TODO add recovery
    p = None
    if diff_cache:
        try:
            parser_cache_item = utils.parser_cache[path]
        except KeyError:
            pass
        else:
            p = parser_cache_item.parser
            lines = splitlines(code, keepends=True)
            new_node = DiffParser(p).update(lines)
            p._parsed = new_node
            utils.save_parser(grammar, path, p, pickling=False)
            if added_newline:
                p.source = code[:-1]
                _remove_last_newline(new_node)
            return new_node
    p = parser(grammar, code, **kwargs)
    new_node = p.parse(tokens=tokens)
    if added_newline:
        _remove_last_newline(new_node)
        p.source = code[:-1]

    if use_cache or diff_cache:
        utils.save_parser(grammar, path, p)
    return new_node
