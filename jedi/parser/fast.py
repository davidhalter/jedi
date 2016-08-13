"""
Basically a parser that is faster, because it tries to parse only parts and if
anything changes, it only reparses the changed parts. But because it's not
finished (and still not working as I want), I won't document it any further.
"""
import re
from itertools import chain
import difflib

from jedi._compatibility import use_metaclass
from jedi import settings
from jedi.common import splitlines
from jedi.parser import ParserWithRecovery
from jedi.parser import tree
from jedi.parser.utils import underscore_memoization, parser_cache
from jedi.parser import tokenize
from jedi import debug
from jedi.parser.tokenize import (generate_tokens, NEWLINE,
                                  ENDMARKER, INDENT, DEDENT)


class CachedFastParser(type):
    """ This is a metaclass for caching `FastParser`. """
    def __call__(self, grammar, source, module_path=None):
        pi = parser_cache.get(module_path, None)
        if pi is None or not settings.fast_parser:
            return ParserWithRecovery(grammar, source, module_path)

        parser = pi.parser
        d = DiffParser(parser)
        d.update(splitlines(source, keepends=True))
        return parser


class FastParser(use_metaclass(CachedFastParser)):
    pass


class DiffParser():
    def __init__(self, parser):
        self._parser = parser
        self._module = parser.get_root_node()

    def _reset(self):
        self._delete_count = 0
        self._insert_count = 0

        self._parsed_until_line = 0

    def update(self, lines_new):
        '''
        The algorithm works as follows:

        Equal:
            - Assure that the start is a newline, otherwise parse until we get
              one.
            - Copy from parsed_until_line + 1 to max(i2 + 1)
            - Make sure that the indentation is correct (e.g. add DEDENT)
            - Add old and change positions
        Insert:
            - Parse from parsed_until_line + 1 to min(j2 + 1), hopefully not
              much more.
        Always:
            - Set parsed_until_line
        '''
        self._lines_new = lines_new
        self._reset()

        self._old_children = self._module.children
        self._new_children = []
        self._prefix = ''

        lines_old = splitlines(self._parser.source, keepends=True)
        sm = difflib.SequenceMatcher(None, lines_old, lines_new)
        for operation, i1, i2, j1, j2 in sm.get_opcodes():
            print(operation)
            if operation == 'equal':
                line_offset = j1 - i1
                self._copy_from_old_parser(line_offset, i2 + 1, j2 + 1)
            elif operation == 'replace':
                self._delete_count += 1
                self._insert(j2 + 1)
            elif operation == 'insert':
                self._insert(j2 + 1)
            else:
                assert operation == 'delete'
                self._delete_count += 1  # For statistics

    def _copy_from_old_parser(self, line_offset, until_line_old, until_line_new):
        while until_line_new < self._parsed_until_line:
            parsed_until_line_old = self._parsed_until_line + line_offset
            if matches:
                # TODO check missing indent/dedent
                _copy_p()
                self._update_positions(line_offset)
                # We have copied as much as possible (but definitely not too
                # much). Therefore we escape, even if we're not at the end. The
                # rest will be parsed.
                # Might not reach until the end, because there's a statement
                # that is not finished.
                break
            else:
                # Parse 1 line at least. We don't need more, because we just
                # want to get into a state where the old parser has starting
                # statements again (not e.g. lines within parentheses).
                self._parse(self._parsed_until_line + 1)

    def _update_positions(self, line_offset, line_start, line_end):
        if line_offset == 0:
            return

        # Find start node:
        node = self._parser.get_pared_node()
        while True:
            return node

    def _insert(self, until_line_new):
        self._insert_count += 1
        self._parse(until_line_new)

    def _get_before_insertion_node(self):
        if not self._new_children:
            return None

        leaf = self._module.get_leaf_for_position((line, 0), include_prefixes=False)
        while leaf.type != 'newline':
            try:
                leaf = leaf.get_previous_leaf()
            except IndexError:
                # TODO
                raise NotImplementedError

        node = leaf
        while True:
            parent = node.parent
            print(parent)
            if parent.type in ('suite', 'file_input'):
                print(node)
                print(i, line, node.end_pos)
                assert node.end_pos[0] <= line
                assert node.end_pos[1] == 0
                return node
            node = parent

    def _parse(self, until_line):
        """
        Parses at least until the given line, but might just parse more until a
        valid state is reached.
        """
        while until_line > self._parsed_until_line:
            node = self._parse_scope_part(before_node, until_line)
            first_leaf = node.first_leaf()

            before_node = self._get_before_insertion_node()
            if before_node is None:
                # The start of the file.
                self.new_children += node.children
            else:
                before_node.parent.children += node.children

    def _parse_scope_node(self, before_node, until_line, line_offset=0):
        # TODO speed up, shouldn't copy the whole thing all the time.
        # memoryview?
        lines_after = self._lines_new[self._parsed_until_line + 1:]
        tokenizer = self._diff_tokenize(lines_after, until_line, line_offset)
        self._parser = ParserWithRecovery(
            self._parser._grammar,
            source=None,
            tokenizer=tokenizer,
            start_parsing=False
        )
        return self._parser.parse()

    def _diff_tokenize(lines, until_line, line_offset=0):
        is_first_token = True
        omited_first_indent = False
        indent_count = 0
        tokens = generate_tokens(lambda: next(l, ''))
        for token_info in tokens:
            typ = token_info.type
            if typ == 'indent':
                indent_count += 1
                if is_first_token:
                    omited_first_indent = True
                    # We want to get rid of indents that are only here because
                    # we only parse part of the file. These indents would only
                    # get parsed as error leafs, which doesn't make any sense.
                    continue
            elif typ == 'dedent':
                indent_count -= 1
                if omited_first_indent and indent_count == 0:
                    # We are done here, only thing that can come now is an
                    # endmarker or another dedented code block.
                    break
            elif typ == 'newline' and token_info.start_pos[0] >= until_line:
                yield token_info
                x = self.
                import pdb; pdb.set_trace()
                break

            is_first_token = False
            if line_offset != 0:
                raise NotImplementedError
                yield tokenize.TokenInfo(*token_info.string[1:])
            else:
                yield token_info

        yield tokenize.TokenInfo(tokenize.ENDMARKER, *token_info.string[1:])
