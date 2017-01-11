"""
Basically a contains parser that is faster, because it tries to parse only
parts and if anything changes, it only reparses the changed parts.

It works with a simple diff in the beginning and will try to reuse old parser
fragments.
"""
import copy
import re
import difflib

from jedi._compatibility import use_metaclass
from jedi import settings
from jedi.common import splitlines
from jedi.parser import ParserWithRecovery
from jedi.parser.tree import Module, search_ancestor, EndMarker, Flow
from jedi.parser.utils import parser_cache
from jedi import debug
from jedi.parser.tokenize import (generate_tokens, NEWLINE, TokenInfo,
                                  ENDMARKER, INDENT, DEDENT)


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


def _merge_used_names(base_dict, other_dict):
    for key, names in other_dict.items():
        base_dict.setdefault(key, []).extend(names)


def _get_last_line(node_or_leaf):
    last_leaf = node_or_leaf.last_leaf()
    if last_leaf.type == 'error_leaf':
        typ = last_leaf.original_type
    else:
        typ = last_leaf.type
    if typ == 'newline':
        return last_leaf.start_pos[0]
    else:
        return last_leaf.end_pos[0]


def _flows_finished(grammar, stack):
    """
    if, while, for and try might not be finished, because another part might
    still be parsed.
    """
    for dfa, newstate, (symbol_number, nodes) in stack:
        if grammar.number2symbol[symbol_number] in ('if_stmt', 'while_stmt',
                                                    'for_stmt', 'try_stmt'):
            return False
    return True


def suite_or_file_input_is_valid(grammar, stack):
    if not _flows_finished(grammar, stack):
        return False

    for dfa, newstate, (symbol_number, nodes) in reversed(stack):
        if grammar.number2symbol[symbol_number] == 'suite':
            # If only newline is in the suite, the suite is not valid, yet.
            return len(nodes) > 1
    # Not reaching a suite means that we're dealing with file_input levels
    # where there's no need for a valid statement in it. It can also be empty.
    return True


def _is_flow_node(node):
    try:
        value = node.children[0].value
    except AttributeError:
        return False
    return value in ('if', 'for', 'while', 'try')


def _last_leaf_is_newline(last_leaf):
    if last_leaf.prefix.endswith('\n'):
        return True
    if last_leaf.prefix:
        return False
    previous_leaf = last_leaf.get_previous_leaf()
    return (previous_leaf.type == 'newline' or
            previous_leaf.type == 'error_leaf' and
            previous_leaf.original_type == 'newline')


def _update_positions(nodes, line_offset):
    for node in nodes:
        try:
            children = node.children
        except AttributeError:
            # Is a leaf
            node.start_pos = node.start_pos[0] + line_offset, node.start_pos[1]
        else:
            _update_positions(children, line_offset)


class DiffParser(object):
    endmarker_type = 'endmarker'

    def __init__(self, parser):
        self._parser = parser
        self._grammar = self._parser._grammar
        self._old_module = parser.get_root_node()

    def _reset(self):
        self._copy_count = 0
        self._parser_count = 0

        self._parsed_until_line = 0
        self._copied_ranges = []

        self._old_children = self._old_module.children
        self._new_children = []
        self._new_module = Module(self._new_children)
        self._new_module.path = self._old_module.path
        self._new_module.used_names = {}
        self._prefix = ''
        self._last_prefix = ''

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
        sm = difflib.SequenceMatcher(None, lines_old, self._parser_lines_new)
        debug.dbg('diff: line_lengths old: %s, new: %s' % (len(lines_old), line_length))
        for operation, i1, i2, j1, j2 in sm.get_opcodes():
            debug.dbg('diff %s old[%s:%s] new[%s:%s]',
                      operation, i1 + 1, i2, j1 + 1, j2)

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
        self._cleanup()
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
                # want to get into a state where the old parser has statements
                # again that can be copied (e.g. not lines within parentheses).
                self._parse(self._parsed_until_line + 1)
            else:
                p_children = line_stmt.parent.children
                index = p_children.index(line_stmt)

                # Match all the nodes that are in the wanted range.
                nodes = self._divide_nodes(p_children[index:], until_line_old)
                if nodes:
                    self._copy_count += 1
                    _update_positions(nodes, line_offset)
                    self._insert_nodes(nodes)

                    from_ = nodes[0].get_start_pos_of_prefix()[0]
                    to = _get_last_line(nodes[-1])
                    self._copied_ranges.append((from_, to))

                    debug.dbg('diff actually copy %s to %s', from_, to)
                # We have copied as much as possible (but definitely not too
                # much). Therefore we just parse the rest.
                # We might not reach the end, because there's a statement
                # that is not finished.
                self._parse(until_line_new)
                break

    def _get_old_line_stmt(self, old_line):
        leaf = self._old_module.get_leaf_for_position((old_line, 0), include_prefixes=True)

        if leaf.type == 'newline':
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

    def _insert_nodes(self, nodes):
        """
        Returns the scope that a node is a part of.
        """
        # Needs to be done before resetting the parsed
        before_node = self._get_before_insertion_node()

        last_leaf = nodes[-1].last_leaf()
        is_endmarker = last_leaf.type == self.endmarker_type
        self._last_prefix = ''
        if is_endmarker:
            self._parsed_until_line = last_leaf.start_pos[0]
            try:
                separation = last_leaf.prefix.rindex('\n')
            except ValueError:
                pass
            else:
                # Remove the whitespace part of the prefix after a newline.
                # That is not relevant if parentheses were opened. Always parse
                # until the end of a line.
                last_leaf.prefix, self._last_prefix = \
                    last_leaf.prefix[:separation + 1], last_leaf.prefix[separation + 1:]

            if _last_leaf_is_newline(last_leaf):
                self._parsed_until_line -= 1
        else:
            if last_leaf.type == 'newline':
                # Newlines end on the next line, which means that they would cover
                # the next line. That line is not fully parsed at this point.
                self._parsed_until_line = last_leaf.start_pos[0]
            else:
                self._parsed_until_line = last_leaf.end_pos[0]
        debug.dbg('set parsed_until %s', self._parsed_until_line)

        first_leaf = nodes[0].first_leaf()
        first_leaf.prefix = self._prefix + first_leaf.prefix
        self._prefix = ''

        if is_endmarker:
            self._prefix = last_leaf.prefix

            nodes = nodes[:-1]
            if not nodes:
                return self._new_module

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
                    # A suite starts with NEWLINE, ...
                    indentation = p_children[1].start_pos[1]
                else:
                    indentation = p_children[0].start_pos[1]

                if line_indentation < indentation:  # Dedent
                    # We might be at the most outer layer: modules. We
                    # don't want to depend on the first statement
                    # having the right indentation.
                    if new_parent.parent is not None:
                        new_parent = search_ancestor(
                            new_parent,
                            ('suite', 'file_input')
                        )
                        continue

                p_children += nodes
                assert new_parent.type in ('suite', 'file_input')
                break

        # Reset the parents
        for node in nodes:
            node.parent = new_parent
        if new_parent.type == 'suite':
            return new_parent.get_parent_scope()

        return new_parent

    def _get_before_insertion_node(self):
        if not self._new_children:
            return None

        line = self._parsed_until_line + 1
        node = self._new_module.last_leaf()
        while True:
            parent = node.parent
            if parent.type in ('suite', 'file_input'):
                assert node.end_pos[0] <= line
                assert node.end_pos[1] == 0 or '\n' in self._prefix
                return node
            node = parent

    def _divide_node(self, node, until_line):
        if node.type not in ('classdef', 'funcdef'):
            return None

        suite = node.children[-1]
        if suite.type != 'suite':
            return None

        nodes = self._divide_nodes(suite.children, until_line)

        if len(nodes) < 2:
            # A suite only with newline is not valid.
            return None

        new_node = copy.copy(node)
        new_suite = copy.copy(suite)

        # And now set the correct parents
        for child in nodes:
            child.parent = new_suite
        new_suite.children = nodes

        new_node.children = list(new_node.children)
        new_node.children[-1] = new_suite
        for child in new_node.children:
            child.parent = new_node
        return new_node

    def _copy_divided_nodes(self, nodes):
        parent = nodes[-1].last_leaf().get_parent_scope()
        if parent == nodes[0].get_parent_scope():
            check_nodes = nodes
        else:
            n = parent
            while n is not None:
                if isinstance(n, Flow):
                    parent = n.get_parent_scope()
                n = n.parent
            check_nodes = parent.children

        last_node = check_nodes[-1]

        if last_node.type == 'suite':
            parent = last_node
            check_nodes = parent.children
            last_node = check_nodes[-1]

        drop_node_count = 0
        if last_node.type in ('error_leaf', 'error_node') or _is_flow_node(last_node):
            # Error leafs/nodes don't have a defined start/end. Error
            # nodes might not end with a newline (e.g. if there's an
            # open `(`). Therefore ignore all of them unless they are
            # succeeded with valid parser state.
            # If we copy flows at the end, they might be continued
            # after the copy limit (in the new parser).
            n = last_node
            # In this while loop we try to remove until we find a newline.
            while True:
                drop_node_count += 1
                try:
                    n = check_nodes[-drop_node_count - 1]
                except IndexError:
                    break
                if n.last_leaf().type == 'newline':
                    break

        if drop_node_count:
            node = self._drop_last_node(nodes[-1], last_node, drop_node_count)
            if node is None:
                nodes = nodes[:-drop_node_count]
            else:
                nodes[-1] = node
        return nodes

    def _drop_last_node(self, base_node, last_node_to_drop, drop_node_count):
        if base_node == last_node_to_drop:
            return None

        last_node = base_node.children[-1]
        child = self._drop_last_node(last_node, last_node_to_drop, drop_node_count)

        base_node = copy.copy(base_node)
        if child is None:
            if base_node.type == 'suite' and len(base_node.children) <= 1 + drop_node_count:
                return None
            if base_node.type in ('classdef', 'funcdef'):
                return None

            base_node.children = base_node.children[:-drop_node_count]
        else:
            base_node.children = list(base_node.children)
            base_node.children[-1] = child
            child.parent = base_node

        for c in base_node.children:
            c.parent = base_node
        return base_node

    def _divide_nodes(self, nodes, until_line):
        """
        Breaks up scopes and returns only the part until the given line.

        Tries to get the parts it can safely get and ignores the rest.
        """
        new_nodes = []
        for i, child in enumerate(nodes):
            # TODO this check might take a bit of time for large files. We
            # might want to change this to do more intelligent guessing or
            # binary search.
            if _get_last_line(child) > until_line:
                node = self._divide_node(child, until_line)
                if node is not None:
                    new_nodes.append(node)
                break
            else:
                new_nodes.append(child)

        if new_nodes:
            return self._copy_divided_nodes(new_nodes)
        return new_nodes

    def _parse(self, until_line):
        """
        Parses at least until the given line, but might just parse more until a
        valid state is reached.
        """
        while until_line > self._parsed_until_line:
            node = self._try_parse_part(until_line)
            nodes = self._get_children_nodes(node)
            self._insert_nodes(nodes)
            _merge_used_names(
                self._new_module.used_names,
                node.used_names
            )

    def _get_children_nodes(self, node):
        nodes = node.children
        first_element = nodes[0]
        # TODO this looks very strange...
        if first_element.type == 'error_leaf' and \
                first_element.original_type == 'indent':
            assert False, str(nodes)
            #assert nodes[-1].type == 'dedent'
            ## This means that the start and end leaf
            #nodes = nodes[1:-1] + [nodes[-1]]

        return nodes

    def _try_parse_part(self, until_line):
        """
        Sets up a normal parser that uses a spezialized tokenizer to only parse
        until a certain position (or a bit longer if the statement hasn't
        ended.
        """
        self._parser_count += 1
        # TODO speed up, shouldn't copy the whole list all the time.
        # memoryview?
        lines_after = self._parser_lines_new[self._parsed_until_line:]
        #print('parse_content', self._parsed_until_line, lines_after, until_line)
        tokenizer = self._diff_tokenize(
            lines_after,
            until_line,
            line_offset=self._parsed_until_line
        )
        self._active_parser = ParserWithRecovery(
            self._grammar,
            source='\n',
            start_parsing=False
        )
        return self._active_parser.parse(tokenizer=tokenizer)

    def _cleanup(self):
        """Add used names and an end marker."""
        # Add the used names from the old parser to the new one.
        copied_line_numbers = set()
        for l1, l2 in self._copied_ranges:
            copied_line_numbers.update(range(l1, l2 + 1))

        new_used_names = self._new_module.used_names
        for key, names in self._old_module.used_names.items():
            for name in names:
                if name.start_pos[0] in copied_line_numbers:
                    new_used_names.setdefault(key, []).append(name)

        # Add an endmarker.
        try:
            last_leaf = self._new_module.last_leaf()
            end_pos = list(last_leaf.end_pos)
        except IndexError:
            end_pos = [1, 0]
        lines = splitlines(self._prefix)
        assert len(lines) > 0
        if len(lines) == 1:
            end_pos[1] += len(lines[0])
        else:
            end_pos[0] += len(lines) - 1
            end_pos[1] = len(lines[-1])

        endmarker = EndMarker('', tuple(end_pos), self._prefix + self._last_prefix)
        endmarker.parent = self._new_module
        self._new_children.append(endmarker)

    def _diff_tokenize(self, lines, until_line, line_offset=0):
        is_first_token = True
        omitted_first_indent = False
        indents = []
        l = iter(lines)
        tokens = generate_tokens(lambda: next(l, ''), use_exact_op_types=True)
        stack = self._active_parser.pgen_parser.stack
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

            if typ == DEDENT:
                indents.pop()
                if omitted_first_indent and not indents:
                    # We are done here, only thing that can come now is an
                    # endmarker or another dedented code block.
                    typ, string, start_pos, prefix = next(tokens)
                    if '\n' in prefix:
                        prefix = re.sub(r'(<=\n)[^\n]+$', '', prefix)
                    else:
                        prefix = ''
                    yield TokenInfo(ENDMARKER, '', (start_pos[0] + line_offset, 0), prefix)
                    break
            elif typ == NEWLINE and start_pos[0] >= until_line:
                yield TokenInfo(typ, string, start_pos, prefix)
                # Check if the parser is actually in a valid suite state.
                if suite_or_file_input_is_valid(self._grammar, stack):
                    start_pos = start_pos[0] + 1, 0
                    while len(indents) > int(omitted_first_indent):
                        indents.pop()
                        yield TokenInfo(DEDENT, '', start_pos, '')

                    yield TokenInfo(ENDMARKER, '', start_pos, '')
                    break
                else:
                    continue

            yield TokenInfo(typ, string, start_pos, prefix)
