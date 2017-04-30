"""
Parsers for Python
"""
import os

from jedi import settings
from jedi._compatibility import FileNotFoundError
from jedi.parser.pgen2.pgen import generate_grammar
from jedi.parser.python.parser import Parser, _remove_last_newline
from jedi.parser.python.diff import DiffParser
from jedi.parser.tokenize import generate_tokens
from jedi.parser.cache import parser_cache, load_module, save_module
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
    :param grammar: A Python grammar file, created with load_grammar. You may
        not specify it. In that case it's the current Python version.
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

    if cache and not code and path is not None:
        # In this case we do actual caching. We just try to load it.
        module_node = load_module(grammar, path)
        if module_node is not None:
            return module_node

    if code is None:
        with open(path, 'rb') as f:
            code = source_to_unicode(f.read())

    if diff_cache and settings.fast_parser:
        try:
            module_cache_item = parser_cache[path]
        except KeyError:
            pass
        else:
            lines = splitlines(code, keepends=True)
            module_node = module_cache_item.node
            old_lines = module_cache_item.lines
            if old_lines == lines:
                save_module(grammar, path, module_node, lines, pickling=False)
                return module_node

            new_node = DiffParser(grammar, module_node).update(
                old_lines=old_lines,
                new_lines=lines
            )
            save_module(grammar, path, new_node, lines, pickling=cache)
            return new_node

    added_newline = not code.endswith('\n')
    lines = tokenize_lines = splitlines(code, keepends=True)
    if added_newline:
        code += '\n'
        tokenize_lines = list(tokenize_lines)
        tokenize_lines[-1] += '\n'
        tokenize_lines.append('')

    tokens = generate_tokens(tokenize_lines, use_exact_op_types=True)

    p = Parser(grammar, error_recovery=error_recovery, start_symbol=start_symbol)
    root_node = p.parse(tokens=tokens)
    if added_newline:
        _remove_last_newline(root_node)

    if cache or diff_cache:
        save_module(grammar, path, root_node, lines, pickling=cache)
    return root_node
