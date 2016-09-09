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
from jedi.parser.tree import Module, search_ancestor, EndMarker
from jedi.parser.utils import parser_cache
from jedi.parser import tokenize
from jedi import debug
from jedi.parser.tokenize import (generate_tokens, NEWLINE,
                                  ENDMARKER, INDENT, DEDENT, tok_name)


class CachedFastParser(type):
    """ This is a metaclass for caching `FastParser`. """
    def __call__(self, grammar, source, module_path=None):
        pi = parser_cache.get(module_path, None)
        if pi is None or not settings.fast_parser:
            return ParserWithRecovery(grammar, source, module_path)

        parser = pi.parser
        d = DiffParser(parser)
        new_lines = splitlines(source, keepends=True)
        parser.module = parser._parsed = d.update(new_lines)
        return parser


class FastParser(use_metaclass(CachedFastParser)):
    pass


def _merge_names_dicts(base_dict, other_dict):
    for key, names in other_dict.items():
        base_dict.setdefault(key, []).extend(names)


def suite_or_file_input_is_valid(parser):
    stack = parser.pgen_parser.stack
    for dfa, newstate, (symbol_number, nodes) in reversed(stack):
        if symbol_number == parser._grammar.symbol2number['suite']:
            # If we don't have nodes already, the suite is not valid.
            return bool(nodes)
    # Not reaching a suite means that we're dealing with file_input levels
    # where there's no need for a valid statement in it. It can also be empty.
    return True


class DiffParser(object):
    endmarker_type = 'endmarker'

    def __init__(self, parser):
        self._parser = parser
        self._old_module = parser.get_root_node()

    def _reset(self):
        self._copy_count = 0
        self._parser_count = 0

        self._parsed_until_line = 0
        self._copied_ranges = []

        self._old_children = self._old_module.children
        self._new_children = []
        self._new_module = Module(self._new_children)
        # TODO get rid of Module.global_names in evaluator. It's getting ignored here.
        self._new_module.path = self._old_module.path
        self._new_module.names_dict = {}
        self._new_module.used_names = {}
        self._new_module.global_names = []
        self._prefix = ''

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

        Returns the new module node.
        '''
        self._parser_lines_new = lines_new
        self._added_newline = False
        if lines_new[-1] != '':
            # The Python grammar needs a newline at the end of a file, but for
            # everything else we keep working with lines_new here.
            self._parser_lines_new = list(lines_new)
            self._parser_lines_new[-1] += '\n'
            self._added_newline = True

        self._reset()

        line_length = len(lines_new)
        lines_old = splitlines(self._parser.source, keepends=True)
        sm = difflib.SequenceMatcher(None, lines_old, lines_new)
        print(len(lines_old), line_length, lines_old, lines_new)
        for operation, i1, i2, j1, j2 in sm.get_opcodes():
            print('\t\t', operation, i1, i2, j1, j2)
            if j2 == line_length + int(self._added_newline):
                # The empty part after the last newline is not relevant.
                j2 -= 1

            if operation == 'equal':
                line_offset = j1 - i1
                self._copy_from_old_parser(line_offset, i2, j2)
            elif operation == 'replace':
                self._parse(until_line=j2)
            elif operation == 'insert':
                self._parse(until_line=j2)
            else:
                assert operation == 'delete'

        # Cleanup (setting endmarker, used_names)
        self._post_parse()
        if self._added_newline:
            self._parser.module = self._parser._parsed = self._new_module
            self._parser.remove_last_newline()
            self._parsed_until_line -= 1

        self._parser.source = ''.join(lines_new)
        self._old_module = self._new_module

        assert self._new_module.end_pos[0] == line_length
        return self._new_module

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
                print('copy', line_stmt.end_pos, parsed_until_line_old, until_line_old, line_stmt)
                p_children = line_stmt.parent.children
                index = p_children.index(line_stmt)
                nodes = []
                for node in p_children[index:]:
                    last_leaf = node.last_leaf()
                    if last_leaf.type == 'newline':
                        last_line = last_leaf.start_pos[0]
                    else:
                        last_line = last_leaf.end_pos[0]

                    print('test', last_line, until_line_old, node)
                    if last_line > until_line_old:
                        divided_node = self._divide_node(node, until_line_new)
                        print('divided', divided_node)
                        if divided_node is not None:
                            nodes.append(divided_node)
                        break
                    else:
                        nodes.append(node)

                if nodes:
                    print('COPY', until_line_new)
                    self._copy_count += 1
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
        node = self._parser.get_parsed_node()
        while True:
            return node

    def _insert_nodes(self, nodes):
        """
        Returns the scope that a node is a part of.
        """
        # Needs to be done before resetting the parsed
        before_node = self._get_before_insertion_node()

        last_leaf = nodes[-1].last_leaf()
        is_endmarker = last_leaf.type == self.endmarker_type
        last_non_endmarker = last_leaf
        if is_endmarker:
            try:
                last_non_endmarker = last_leaf.get_previous_leaf()
            except IndexError:
                # If the parsed part is empty, nevermind and continue with the
                # endmarker.
                pass

        while last_non_endmarker.type == 'dedent':
            last_non_endmarker = last_non_endmarker.get_previous_leaf()
        if last_non_endmarker.type == 'newline':
            # Newlines end on the next line, which means that they would cover
            # the next line. That line is not fully parsed at this point.
            self._parsed_until_line = last_leaf.start_pos[0]
        else:
            self._parsed_until_line = last_leaf.end_pos[0]
        print('parsed_until', last_leaf.end_pos, self._parsed_until_line)

        first_leaf = nodes[0].first_leaf()
        first_leaf.prefix = self._prefix + first_leaf.prefix
        self._prefix = ''
        if is_endmarker:
            self._prefix = last_leaf.prefix

            nodes = nodes[:-1]
            if not nodes:
                return self._new_module
        print("insert_nodes", nodes)

        # Now the preparations are done. We are inserting the nodes.
        if before_node is None:  # Everything is empty.
            self._new_children += nodes
            new_parent = self._new_module
        else:
            assert nodes[0].type != 'newline'
            line_indentation = nodes[0].start_pos[1]
            new_parent = before_node.parent
            while True:
                p_children = new_parent.children
                if new_parent.type == 'suite':
                    # A suite starts with NEWLINE, INDENT, ...
                    indentation = p_children[2].start_pos[1]
                else:
                    indentation = p_children[0].start_pos[1]

                if line_indentation < indentation:  # Dedent
                    # We might be at the most outer layer: modules. We
                    # don't want to depend on the first statement
                    # having the right indentation.
                    if new_parent.parent is not None:
                        # TODO add dedent
                        new_parent = search_ancestor(
                            new_parent,
                            ('suite', 'file_input')
                        )
                        continue

                # TODO check if the indentation is lower than the last statement
                # and add a dedent error leaf.
                # TODO do the same for indent error leafs.
                p_children += nodes
                assert new_parent.type in ('suite', 'file_input')
                break

        # Reset the parents
        for node in nodes:
            print('reset', node)
            node.parent = new_parent
        if new_parent.type == 'suite':
            return new_parent.get_parent_scope()

        return new_parent

    def _get_before_insertion_node(self):
        if not self._new_children:
            return None

        line = self._parsed_until_line + 1
        leaf = self._new_module.last_leaf()
        while leaf.type == 'dedent':
            leaf = leaf.get_previous_leaf()
        node = leaf
        while True:
            parent = node.parent
            print('get_ins', parent)
            if parent.type in ('suite', 'file_input'):
                print('get_ins', node)
                print('get_ins', line, node.end_pos)
                assert node.end_pos[0] <= line
                assert node.end_pos[1] == 0
                return node
            node = parent

    def _update_names_dict(self, scope_node, nodes):
        assert scope_node.type in ('suite', 'file_input')

        names_dict = scope_node.names_dict

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

    def _merge_parsed_node(self, scope_node, parsed_node):
        _merge_names_dicts(scope_node.names_dict, parsed_node.names_dict)
        _merge_names_dicts(self._new_module.used_names, parsed_node.used_names)

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
        for child in new_node.children:
            child.parent = new_node
        for i, child in enumerate(new_suite.children):
            child.parent = new_suite
            if child.end_pos[1] > until_line:
                divided_node = self._divide_node(child, until_line)
                new_suite.children = new_suite.children[:i]
                if divided_node is not None:
                    new_suite.children.append(divided_node)
                    divided_node.parent = new_suite
                if len(new_suite.children) < 3:
                    # A suite only with newline and indent is not valid.
                    return None
                break
        return new_node

    def _get_old_line_stmt(self, old_line):
        leaf = self._old_module.get_leaf_for_position((old_line, 0), include_prefixes=True)
        if leaf.type == 'newline':
            leaf = leaf.get_next_leaf()
        while leaf.type == 'dedent':
            leaf = leaf.get_next_leaf()
        if leaf.get_start_pos_of_prefix()[0] == old_line:
            node = leaf
            # TODO use leaf.get_definition one day when that one is working
            # well.
            while node.parent.type not in ('file_input', 'suite'):
                node = node.parent
            return node
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
            #if until_line - 1 == len(self._parser_lines_new):
                # We are done in any case. This is special case, because the l
                #return

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
        self._parser_count += 1
        print('PARSE', self._parsed_until_line, until_line)
        # TODO speed up, shouldn't copy the whole list all the time.
        # memoryview?
        lines_after = self._parser_lines_new[self._parsed_until_line:]
        print('parse_content', self._parsed_until_line, lines_after, until_line)
        tokenizer = self._diff_tokenize(
            lines_after,
            until_line,
            line_offset=self._parsed_until_line
        )
        self._active_parser = ParserWithRecovery(
            self._parser._grammar,
            source='\n',
            start_parsing=False
        )
        return self._active_parser.parse(tokenizer=tokenizer)

    def _post_parse(self):
        # Add the used names from the old parser to the new one.
        copied_line_numbers = set()
        for l1, l2 in self._copied_ranges:
            copied_line_numbers.update(range(l1, l2 + 1))

        new_used_names = self._new_module.used_names
        for key, names in self._old_module.used_names.items():
            for name in names:
                if name.start_pos[0] in copied_line_numbers:
                    new_used_names.setdefault(key, []).add(name)

        # Add an endmarker.
        last_leaf = self._new_module.last_leaf()
        while last_leaf.type == 'dedent':
            last_leaf = last_leaf.get_previous_leaf()

        end_pos = list(last_leaf.end_pos)
        lines = splitlines(self._prefix)
        assert len(lines) > 0
        if len(lines) == 1:
            end_pos[1] += len(lines[0])
        else:
            end_pos[0] += len(lines) - 1
            end_pos[1] = len(lines[-1])

        endmarker = EndMarker(self._parser.position_modifier, '', tuple(end_pos), self._prefix)
        endmarker.parent = self._new_module
        self._new_children.append(endmarker)

    def _diff_tokenize(self, lines, until_line, line_offset=0):
        is_first_token = True
        omitted_first_indent = False
        indents = []
        l = iter(lines)
        tokens = generate_tokens(lambda: next(l, ''), use_exact_op_types=True)
        for typ, string, start_pos, prefix in tokens:
            start_pos = start_pos[0] + line_offset, start_pos[1]
            if typ == INDENT:
                indents.append(start_pos[1])
                if is_first_token:
                    omitted_first_indent = True
                    # We want to get rid of indents that are only here because
                    # we only parse part of the file. These indents would only
                    # get parsed as error leafs, which doesn't make any sense.
                    is_first_token = False
                    continue
            is_first_token = False

            if typ == tokenize.DEDENT:
                indents.pop()
                if omitted_first_indent and not indents:
                    # We are done here, only thing that can come now is an
                    # endmarker or another dedented code block.
                    yield tokenize.TokenInfo(tokenize.ENDMARKER, '', start_pos, '')
                    break
            elif typ == NEWLINE and start_pos[0] >= until_line:
                yield tokenize.TokenInfo(typ, string, start_pos, prefix)
                # Check if the parser is actually in a valid suite state.
                if suite_or_file_input_is_valid(self._active_parser):
                    start_pos = start_pos[0] + 1, 0
                    while len(indents) > int(omitted_first_indent):
                        indents.pop()
                        yield tokenize.TokenInfo(DEDENT, '', start_pos, '')

                    yield tokenize.TokenInfo(ENDMARKER, '', start_pos, '')
                    break
                else:
                    continue

            print('tok', tok_name[typ], repr(string), start_pos)
            yield tokenize.TokenInfo(typ, string, start_pos, prefix)
