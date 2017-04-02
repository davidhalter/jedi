from jedi.parser.python import tree
from jedi.parser import tokenize
from jedi.parser.token import (DEDENT, INDENT, ENDMARKER, NEWLINE, NUMBER,
                               STRING, tok_name)
from jedi.parser.parser import BaseParser
from jedi.common import splitlines


class Parser(BaseParser):
    """
    This class is used to parse a Python file, it then divides them into a
    class structure of different scopes.

    :param grammar: The grammar object of pgen2. Loaded by load_grammar.
    """

    node_map = {
        'expr_stmt': tree.ExprStmt,
        'classdef': tree.Class,
        'funcdef': tree.Function,
        'file_input': tree.Module,
        'import_name': tree.ImportName,
        'import_from': tree.ImportFrom,
        'break_stmt': tree.KeywordStatement,
        'continue_stmt': tree.KeywordStatement,
        'return_stmt': tree.ReturnStmt,
        'raise_stmt': tree.KeywordStatement,
        'yield_expr': tree.YieldExpr,
        'del_stmt': tree.KeywordStatement,
        'pass_stmt': tree.KeywordStatement,
        'global_stmt': tree.GlobalStmt,
        'nonlocal_stmt': tree.KeywordStatement,
        'print_stmt': tree.KeywordStatement,
        'assert_stmt': tree.AssertStmt,
        'if_stmt': tree.IfStmt,
        'with_stmt': tree.WithStmt,
        'for_stmt': tree.ForStmt,
        'while_stmt': tree.WhileStmt,
        'try_stmt': tree.TryStmt,
        'comp_for': tree.CompFor,
        'decorator': tree.Decorator,
        'lambdef': tree.Lambda,
        'old_lambdef': tree.Lambda,
        'lambdef_nocond': tree.Lambda,
    }
    default_node = tree.PythonNode

    def __init__(self, grammar, error_recovery=True, start_symbol='file_input'):
        super(Parser, self).__init__(grammar, start_symbol, error_recovery=error_recovery)

        self.syntax_errors = []
        self._omit_dedent_list = []
        self._indent_counter = 0

        # TODO do print absolute import detection here.
        # try:
        #     del python_grammar_no_print_statement.keywords["print"]
        # except KeyError:
        #     pass  # Doesn't exist in the Python 3 grammar.

        # if self.options["print_function"]:
        #     python_grammar = pygram.python_grammar_no_print_statement
        # else:

    def parse(self, tokens):
        if self._error_recovery:
            if self._start_symbol != 'file_input':
                raise NotImplementedError

            tokens = self._recovery_tokenize(tokens)

        node = super(Parser, self).parse(tokens)

        if self._start_symbol == 'file_input' != node.type:
            # If there's only one statement, we get back a non-module. That's
            # not what we want, we want a module, so we add it here:
            node = self.convert_node(
                self._grammar,
                self._grammar.symbol2number['file_input'],
                [node]
            )

        return node

    def convert_node(self, grammar, type, children):
        """
        Convert raw node information to a PythonBaseNode instance.

        This is passed to the parser driver which calls it whenever a reduction of a
        grammar rule produces a new complete node, so that the tree is build
        strictly bottom-up.
        """
        # TODO REMOVE symbol, we don't want type here.
        symbol = grammar.number2symbol[type]
        try:
            return self.node_map[symbol](children)
        except KeyError:
            if symbol == 'suite':
                # We don't want the INDENT/DEDENT in our parser tree. Those
                # leaves are just cancer. They are virtual leaves and not real
                # ones and therefore have pseudo start/end positions and no
                # prefixes. Just ignore them.
                children = [children[0]] + children[2:-1]
            return self.default_node(symbol, children)

    def convert_leaf(self, grammar, type, value, prefix, start_pos):
        # print('leaf', repr(value), token.tok_name[type])
        if type == tokenize.NAME:
            if value in grammar.keywords:
                return tree.Keyword(value, start_pos, prefix)
            else:
                return tree.Name(value, start_pos, prefix)
        elif type == STRING:
            return tree.String(value, start_pos, prefix)
        elif type == NUMBER:
            return tree.Number(value, start_pos, prefix)
        elif type == NEWLINE:
            return tree.Newline(value, start_pos, prefix)
        elif type == ENDMARKER:
            return tree.EndMarker(value, start_pos, prefix)
        else:
            return tree.Operator(value, start_pos, prefix)

    def error_recovery(self, grammar, stack, arcs, typ, value, start_pos, prefix,
                       add_token_callback):
        """
        This parser is written in a dynamic way, meaning that this parser
        allows using different grammars (even non-Python). However, error
        recovery is purely written for Python.
        """
        if not self._error_recovery:
            return super(Parser, self).error_recovery(
                grammar, stack, arcs, typ, value, start_pos, prefix,
                add_token_callback)

        def current_suite(stack):
            # For now just discard everything that is not a suite or
            # file_input, if we detect an error.
            for index, (dfa, state, (type_, nodes)) in reversed(list(enumerate(stack))):
                # `suite` can sometimes be only simple_stmt, not stmt.
                symbol = grammar.number2symbol[type_]
                if symbol == 'file_input':
                    break
                elif symbol == 'suite' and len(nodes) > 1:
                    # suites without an indent in them get discarded.
                    break
                elif symbol == 'simple_stmt' and len(nodes) > 1:
                    # simple_stmt can just be turned into a PythonNode, if
                    # there are enough statements. Ignore the rest after that.
                    break
            return index, symbol, nodes

        index, symbol, nodes = current_suite(stack)
        if symbol == 'simple_stmt':
            index -= 2
            (_, _, (type_, suite_nodes)) = stack[index]
            symbol = grammar.number2symbol[type_]
            suite_nodes.append(tree.PythonNode(symbol, list(nodes)))
            # Remove
            nodes[:] = []
            nodes = suite_nodes
            stack[index]

        # print('err', token.tok_name[typ], repr(value), start_pos, len(stack), index)
        if self._stack_removal(grammar, stack, arcs, index + 1, value, start_pos):
            add_token_callback(typ, value, start_pos, prefix)
        else:
            if typ == INDENT:
                # For every deleted INDENT we have to delete a DEDENT as well.
                # Otherwise the parser will get into trouble and DEDENT too early.
                self._omit_dedent_list.append(self._indent_counter)
            else:
                error_leaf = tree.PythonErrorLeaf(tok_name[typ].lower(), value, start_pos, prefix)
                stack[-1][2][1].append(error_leaf)

    def _stack_removal(self, grammar, stack, arcs, start_index, value, start_pos):
        failed_stack = []
        found = False
        all_nodes = []
        for dfa, state, (typ, nodes) in stack[start_index:]:
            if nodes:
                found = True
            if found:
                symbol = grammar.number2symbol[typ]
                failed_stack.append((symbol, nodes))
                all_nodes += nodes
        if failed_stack:
            stack[start_index - 1][2][1].append(tree.PythonErrorNode(all_nodes))

        stack[start_index:] = []
        return failed_stack

    def _recovery_tokenize(self, tokens):
        for typ, value, start_pos, prefix in tokens:
            # print(tokenize.tok_name[typ], repr(value), start_pos, repr(prefix))
            if typ == DEDENT:
                # We need to count indents, because if we just omit any DEDENT,
                # we might omit them in the wrong place.
                o = self._omit_dedent_list
                if o and o[-1] == self._indent_counter:
                    o.pop()
                    continue

                self._indent_counter -= 1
            elif typ == INDENT:
                self._indent_counter += 1

            yield typ, value, start_pos, prefix


def _remove_last_newline(node):
    endmarker = node.children[-1]
    # The newline is either in the endmarker as a prefix or the previous
    # leaf as a newline token.
    prefix = endmarker.prefix
    leaf = endmarker.get_previous_leaf()
    if prefix:
        text = prefix
    else:
        if leaf is None:
            raise ValueError("You're trying to remove a newline from an empty module.")

        text = leaf.value

    if not text.endswith('\n'):
        raise ValueError("There's no newline at the end, cannot remove it.")

    text = text[:-1]
    if prefix:
        endmarker.prefix = text

        if leaf is None:
            end_pos = (1, 0)
        else:
            end_pos = leaf.end_pos

        lines = splitlines(text, keepends=True)
        if len(lines) == 1:
            end_pos = end_pos[0], end_pos[1] + len(lines[0])
        else:
            end_pos = end_pos[0] + len(lines) - 1,  len(lines[-1])
        endmarker.start_pos = end_pos
    else:
        leaf.value = text
        endmarker.start_pos = leaf.end_pos
