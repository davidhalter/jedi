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
    for error_statement in module.error_statements:
        if error_statement.first_type in ('import_from', 'import_name') \
                and error_statement.start_pos < pos <= error_statement.end_pos:
            return importer_from_error_statement(error_statement, pos)
    return None, 0, False, False


def _get_code(code, start_pos, end_pos):
    """
    :param code_start_pos: is where the code starts.
    """
    lines = common.splitlines(code)
    # Get relevant lines.
    lines = lines[start_pos[0] - 1:end_pos[0]]
    # Remove the parts at the end of the line.
    lines[-1] = lines[-1][:end_pos[1]]
    # Remove first line indentation.
    lines[0] = lines[0][start_pos[1]:]
    return '\n'.join(lines)


def get_user_or_error_stmt(module, position):
    user_stmt = module.get_statement_for_position(position)
    if user_stmt is None or user_stmt.type == 'whitespace':
        # If there's no error statement and we're just somewhere, we want
        # completions for just whitespace.
        '''
        for error_stmt in module.error_statements:
            if error_stmt.start_pos < position <= error_stmt.end_pos:
                return error_stmt
'''

    return user_stmt


class OnErrorLeaf(Exception):
    @property
    def error_leaf(self):
        return self.args[0]


def get_stack_at_position(grammar, source, module, pos):
    """
    Returns the possible node names (e.g. import_from, xor_test or yield_stmt).
    """
    user_stmt = get_user_or_error_stmt(module, pos)

    if user_stmt is not None and user_stmt.type in ('indent', 'dedent'):
        code = ''
    else:
        if user_stmt is None:
            user_stmt = module.get_leaf_for_position(pos, include_prefixes=True)
        if pos <= user_stmt.start_pos:
            try:
                leaf = user_stmt.get_previous_leaf()
                print(user_stmt, leaf)
            except IndexError:
                pass
            else:
                user_stmt = get_user_or_error_stmt(module, leaf.start_pos)
                print(user_stmt, leaf.start_pos)
        # Only if were in front of the leaf we want to get the stack,
        # because after there's probably a newline or whatever that would
        # be actually tokenized and is not just prefix.
        if pos <= user_stmt.start_pos:
            try:
                leaf = user_stmt.get_previous_leaf()
            except IndexError:
                # Seems to be the first element.
                pass
            else:
                '''
                for error_stmt in reversed(module.error_statements):
                    if leaf.start_pos <= error_stmt.start_pos <= user_stmt.start_pos:
                        # The leaf appears not to be the last leaf. It's actually an
                        # error statement.
                        user_stmt = error_stmt
                        break
                else:
                    user_stmt = get_user_or_error_stmt(module, leaf.start_pos)
'''

        if user_stmt.type == 'error_leaf':
            # Error leafs cannot be parsed.
            raise OnErrorLeaf(user_stmt)

        code = _get_code(source, user_stmt.start_pos, pos)
        # Remove whitespace at the end. Necessary, because the tokenizer will parse
        # an error token (there's no new line at the end in our case). This doesn't
        # alter any truth about the valid tokens at that position.
        code = code.strip()

    class EndMarkerReached(Exception):
        pass

    def tokenize_without_endmarker(code):
        tokens = tokenize.source_tokens(code, use_exact_op_types=True)
        for token_ in tokens:
            if token_[0] == token.ENDMARKER:
                raise EndMarkerReached()
            elif token_[0] == token.DEDENT:
                # Ignore those. Error statements should not contain them, if
                # they do it's for cases where an indentation happens and
                # before the endmarker we still see them.
                pass
            else:
                yield token_

    print(repr(code), 'x')
    p = parser.Parser(grammar, code, start_parsing=False)
    try:
        p.parse(tokenizer=tokenize_without_endmarker(code))
    except EndMarkerReached:
        return Stack(p.pgen_parser.stack)


class Stack(list):
    def get_node_names(self, grammar):
        for dfa, state, (node_number, nodes) in self:
            yield grammar.number2symbol[node_number]

    def get_nodes(self):
        for dfa, state, (node_number, nodes) in self:
            for node in nodes:
                yield node


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

    inversed_keywords = dict((v, k) for k, v in grammar.keywords.items())
    inversed_tokens = dict((v, k) for k, v in grammar.tokens.items())

    keywords = []
    grammar_labels = []

    def scan_stack(index):
        dfa, state, node = stack[index]
        states, first = dfa
        arcs = states[state]

        for label_index, new_state in arcs:
            if label_index == 0:
                # An accepting state, check the stack below.
                scan_stack(index - 1)
            else:
                add_results(label_index)

    scan_stack(-1)

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
