"""
Helpers for the API
"""
import re
from collections import namedtuple

from jedi import common
from jedi.parser import tree as pt
from jedi.evaluate import imports
from jedi import parser
from jedi.parser import tokenize, token


CompletionParts = namedtuple('CompletionParts', ['path', 'has_dot', 'name'])

def get_completion_parts(path_until_cursor):
    """
    Returns the parts for the completion
    :return: tuple - (path, dot, like)
    """
    match = re.match(r'^(.*?)(\.|)(\w?[\w\d]*)$', path_until_cursor, flags=re.S)
    path, dot, name = match.groups()
    return CompletionParts(path, bool(dot), name)


def sorted_definitions(defs):
    # Note: `or ''` below is required because `module_path` could be
    return sorted(defs, key=lambda x: (x.module_path or '', x.line or 0, x.column or 0))


def get_on_import_stmt(evaluator, user_context, user_stmt, is_like_search=False):
    """
    Resolve the user statement, if it is an import. Only resolve the
    parts until the user position.
    """
    name = user_stmt.name_for_position(user_context.position)
    if name is None:
        return None, None

    i = imports.ImportWrapper(evaluator, name)
    return i, name


def check_error_statements(module, pos):
    for error_statement in module.error_statement_stacks:
        if error_statement.first_type in ('import_from', 'import_name') \
                and error_statement.first_pos < pos <= error_statement.next_start_pos:
            return importer_from_error_statement(error_statement, pos)
    return None, 0, False, False


def get_code_until(code, start_pos, end_pos):
    lines = common.splitlines(code)
    line_difference = end_pos[0] - start_pos[0]
    if line_difference == 0:
        end_line_length = end_pos[1] - start_pos[1]
    else:
        end_line_length = end_pos[1]

    if line_difference > len(lines) or end_line_length > len(lines[-1]):
        raise ValueError("The end_pos seems to be after the code part.")

    new_lines = lines[:line_difference] + [lines[-1][:end_line_length]]
    return '\n'.join(new_lines)


def get_stack_at_position(grammar, module, pos):
    """
    Returns the possible node names (e.g. import_from, xor_test or yield_stmt).
    """
    for error_statement in module.error_statement_stacks:
        if error_statement.first_pos < pos <= error_statement.next_start_pos:
            code = error_statement.get_code()
            code = get_code_until(code, error_statement.first_pos, pos)
            break
    else:
        raise NotImplementedError

    class EndMarkerReached(Exception):
        pass

    def tokenize_without_endmarker(code):
        for token_ in tokenize.source_tokens(code):
            if token_[0] == token.ENDMARKER:
                raise EndMarkerReached()
            else:
                yield token_

    p = parser.Parser(grammar, code, tokenizer=tokenize_without_endmarker(code),
                      start_parsing=False)
    try:
        p.parse()
    except EndMarkerReached:
        return p.pgen_parser.stack


def get_possible_completion_types(grammar, stack):
    def add_results(label_index):
        try:
            grammar_labels.append(inversed_tokens[label_index])
        except KeyError:
            try:
                keywords.append(inversed_keywords[label_index])
            except KeyError:
                t, v = grammar.labels[label_index]
                assert t >= 256
                # See if it's a symbol and if we're in its first set
                inversed_keywords
                itsdfa = grammar.dfas[t]
                itsstates, itsfirst = itsdfa
                for first_label_index in itsfirst.keys():
                    add_results(first_label_index)

    dfa, state, node = stack[-1]
    states, first = dfa
    arcs = states[state]

    inversed_keywords = dict((v, k) for k, v in grammar.keywords.items())
    inversed_tokens = dict((v, k) for k, v in grammar.tokens.items())

    keywords = []
    grammar_labels = []
    for label_index, new_state in arcs:
        add_results(label_index)

    return keywords, grammar_labels


def importer_from_error_statement(error_statement, pos):
    def check_dotted(children):
        for name in children[::2]:
            if name.start_pos <= pos:
                yield name

    names = []
    level = 0
    only_modules = True
    unfinished_dotted = False
    for typ, nodes in error_statement.stack:
        if typ == 'dotted_name':
            names += check_dotted(nodes)
            if nodes[-1] == '.':
                # An unfinished dotted_name
                unfinished_dotted = True
        elif typ == 'import_name':
            if nodes[0].start_pos <= pos <= nodes[0].end_pos:
                # We are on the import.
                return None, 0, False, False
        elif typ == 'import_from':
            for node in nodes:
                if node.start_pos >= pos:
                    break
                elif isinstance(node, pt.Node) and node.type == 'dotted_name':
                    names += check_dotted(node.children)
                elif node in ('.', '...'):
                    level += len(node.value)
                elif isinstance(node, pt.Name):
                    names.append(node)
                elif node == 'import':
                    only_modules = False

    return names, level, only_modules, unfinished_dotted
