"""
Basically a parser that is faster, because it tries to parse only parts and if
anything changes, it only reparses the changed parts. But because it's not
finished (and still not working as I want), I won't document it any further.
"""
import copy
import difflib

from jedi._compatibility import use_metaclass
from jedi import settings
from jedi.common import splitlines
from jedi.parser import ParserWithRecovery
from jedi.parser.tree import Module, search_ancestor
from jedi.parser.utils import parser_cache
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


def _merge_names_dicts(base_dict, other_dict):
    for key, names in other_dict.items():
        base_dict.setdefault(key, []).extend(names)


class DiffParser():
    endmarker_type = 'endmarker'

    def __init__(self, parser):
        self._parser = parser
        self._module = parser.get_root_node()

    def _reset(self):
        self._delete_count = 0
        self._insert_count = 0

        self._parsed_until_line = 0
        self._copied_ranges = []
        self._reset_module()

    def _reset_module(self):
        # TODO get rid of _module.global_names in evaluator. It's getting ignored here.
        self._module.global_names = []
        self._module.names_dict = {}

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
        self._temp_module = Module(self._new_children)
        self._temp_module.names_dict = {}
        self._temp_module.used_names = {}
        self._prefix = ''

        lines_old = splitlines(self._parser.source, keepends=True)
        sm = difflib.SequenceMatcher(None, lines_old, lines_new)
        print(lines_old, lines_new)
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

        self._post_parse()
        self._module.used_names = self._temp_module.used_names
        self._module.children = self._new_children
        # TODO insert endmarker

    def _insert(self, until_line_new):
        self._insert_count += 1
        self._parse(until_line_new)

    def _copy_from_old_parser(self, line_offset, until_line_old, until_line_new):
        while until_line_new > self._parsed_until_line:
            parsed_until_line_old = self._parsed_until_line - line_offset
            line_stmt = self._get_old_line_stmt(parsed_until_line_old + 1)
            if line_stmt is None:
                # Parse 1 line at least. We don't need more, because we just
                # want to get into a state where the old parser has starting
                # statements again (not e.g. lines within parentheses).
                self._parse(self._parsed_until_line + 1)
            else:
                p_children = line_stmt.parent.children
                index = p_children.index(line_stmt)
                nodes = []
                for node in p_children[index:]:
                    if until_line_old < node.end_pos[0]:
                        divided_node = self._divide_node(node)
                        if divided_node is not None:
                            nodes.append(divided_node)
                        break
                    else:
                        nodes.append(node)

                if nodes:
                    parent = self._insert_nodes(nodes)
                    self._update_names_dict(parent, nodes)
                # TODO remove dedent at end
                self._update_positions(nodes, line_offset)
                # We have copied as much as possible (but definitely not too
                # much). Therefore we escape, even if we're not at the end. The
                # rest will be parsed.
                # Might not reach until the end, because there's a statement
                # that is not finished.
                break

    def _update_positions(self, nodes, line_offset):
        for node in nodes:
            try:
                children = node.children
            except AttributeError:
                # Is a leaf
                node.start_pos = node.start_pos[0] + line_offset, node.start_pos[1]
            else:
                self._update_positions(children, line_offset)
        if line_offset == 0:
            return

        # Find start node:
        node = self._parser.get_pared_node()
        while True:
            return node

    def _insert_nodes(self, nodes):
        # Needs to be done before resetting the parsed
        before_node = self._get_before_insertion_node()

        last_leaf = nodes[-1].last_leaf()
        if last_leaf.value == '\n':
            # Newlines end on the next line, which means that they would cover
            # the next line. That line is not fully parsed at this point.
            self._parsed_until_line = last_leaf.end_pos[0] - 1
        else:
            self._parsed_until_line = last_leaf.end_pos[0]

        if last_leaf.type == self.endmarker_type:
            first_leaf = nodes[0].first_leaf()
            first_leaf.prefix = self._prefix + first_leaf.prefix
            self._prefix = last_leaf.prefix

            nodes = nodes[:-1]
            if not nodes:
                return self._module

        # Now the preparations are done. We are inserting the nodes.
        if before_node is None:  # Everything is empty.
            self._new_children += nodes
            parent = self._temp_module
        else:
            line_indentation = nodes[0].start_pos[1]
            while True:
                p_children = before_node.parent.children
                indentation = p_children[0].start_pos[1]

                if line_indentation < indentation:  # Dedent
                    # We might be at the most outer layer: modules. We
                    # don't want to depend on the first statement
                    # having the right indentation.
                    if before_node.parent is not None:
                        # TODO add dedent
                        before_node = search_ancestor(
                            before_node.parent,
                            ('suite', 'file_input')
                        )
                        continue

                # TODO check if the indentation is lower than the last statement
                # and add a dedent error leaf.
                # TODO do the same for indent error leafs.
                p_children += nodes
                parent = before_node.parent
                break

        # Reset the parents
        for node in nodes:
            node.parent = parent
        return parent

    def _update_names_dict(self, parent_node, nodes):
        assert parent_node.type in ('suite', 'file_input')
        if parent_node.type == 'suite':
            parent_node = parent_node.parent

        names_dict = parent_node.names_dict

        def scan(nodes):
            for node in nodes:
                if node.type in ('classdef', 'funcdef'):
                    scan([node.children[1]])
                    continue
                try:
                    scan(node.children)
                except AttributeError:
                    if node.type == 'name':
                        names_dict.setdefault(node.value, []).append(node)

        scan(nodes)

    def _merge_parsed_node(self, parent_node, parsed_node):
        _merge_names_dicts(parent_node.names_dict, parsed_node.names_dict)
        _merge_names_dicts(self._temp_module.used_names, parsed_node.used_names)

    def _divide_node(self, node, until_line):
        """
        Breaks up scopes and returns only the part until the given line.

        Tries to get the parts it can safely get and ignores the rest.
        """
        if node.type not in ('classdef', 'funcdef'):
            return None

        suite = node.children[-1]
        if suite.type != 'suite':
            return None

        new_node = copy.copy(node)
        new_node.children[-1] = new_suite = copy.copy(suite)
        for i, child_node in enumerate(new_suite.children):
            if child_node.end_pos[1] > until_line:
                divided_node = self._divide_node(child_node, until_line)
                if divided_node is not None:
                    new_suite.children[i] = divided_node
                    new_suite.children[i + 1:] = []
                else:
                    new_suite.children[i:] = []
                break
        return new_node

    def _get_before_insertion_node(self):
        if not self._new_children:
            return None

        line = self._parsed_until_line + 1
        leaf = self._module.last_leaf()
        '''
        print(line)
        leaf = self._module.get_leaf_for_position((line, 0), include_prefixes=False)
        while leaf.type != 'newline':
            try:
                leaf = leaf.get_previous_leaf()
            except IndexError:
                # TODO
                raise NotImplementedError

'''
        node = leaf
        while True:
            parent = node.parent
            print(parent)
            if parent.type in ('suite', 'file_input'):
                print(node)
                print(line, node.end_pos)
                assert node.end_pos[0] <= line
                assert node.end_pos[1] == 0
                return node
            node = parent

    def _get_old_line_stmt(self, old_line):
        leaf = self._module.get_leaf_for_position((old_line, 0), include_prefixes=True)
        if leaf.get_start_pos_of_prefix()[0] == old_line:
            return leaf.get_definition()
        # Must be on the same line. Otherwise we need to parse that bit.
        return None

    def _parse(self, until_line):
        """
        Parses at least until the given line, but might just parse more until a
        valid state is reached.
        """
        while until_line > self._parsed_until_line:
            node = self._parse_scope_node(until_line)
            nodes = self._get_children_nodes(node)
            parent = self._insert_nodes(nodes)
            self._merge_parsed_node(parent, node)

    def _get_children_nodes(self, node):
        nodes = node.children
        first_element = nodes[0]
        if first_element.type == 'error_leaf' and \
                first_element.original_type == 'indent':
            assert nodes[-1].type == 'dedent'
            # This means that the start and end leaf
            nodes = nodes[1:-2] + [nodes[-1]]

        return nodes

    def _parse_scope_node(self, until_line):
        # TODO speed up, shouldn't copy the whole list all the time.
        # memoryview?
        lines_after = self._lines_new[self._parsed_until_line + 1:]
        tokenizer = self._diff_tokenize(
            lines_after,
            until_line,
            line_offset=self._parsed_until_line
        )
        self._parser = ParserWithRecovery(
            self._parser._grammar,
            source='\n',
            start_parsing=False
        )
        return self._parser.parse(tokenizer=tokenizer)

    def _post_parse(self):
        # Add the used names from the old parser to the new one.
        copied_line_numbers = set()
        for l1, l2 in self._copied_ranges:
            copied_line_numbers.update(range(l1, l2 + 1))

        new_used_names = self._temp_module.used_names
        for key, names in self._module.used_names.items():
            for name in names:
                if name.start_pos[0] in copied_line_numbers:
                    new_used_names.setdefault(key, []).add(name)

    def _diff_tokenize(self, lines, until_line, line_offset=0):
        is_first_token = True
        omited_first_indent = False
        indent_count = 0
        l = iter(lines)
        tokens = generate_tokens(lambda: next(l, ''))
        for typ, string, start_pos, prefix in tokens:
            start_pos = start_pos[0] + line_offset, start_pos[1]
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
            elif typ == 'newline' and start_pos[0] >= until_line:
                yield tokenize.TokenInfo(typ, string, start_pos, prefix)
                # Check if the parser is actually in a valid suite state.
                if 1:
                    x = self._parser.pgen_parser.stack
                    # TODO check if the parser is in a flow, and let it pass if
                    # so.
                    import pdb; pdb.set_trace()
                    break

            is_first_token = False

            yield tokenize.TokenInfo(typ, string, start_pos, prefix)

        typ, string, start_pos, prefix = next(tokens)
        start_pos = start_pos[0] + line_offset, start_pos[1]
        yield tokenize.TokenInfo(tokenize.ENDMARKER, string, start_pos, prefix)
