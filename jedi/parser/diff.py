"""
Basically a contains parser that is faster, because it tries to parse only
parts and if anything changes, it only reparses the changed parts.

It works with a simple diff in the beginning and will try to reuse old parser
fragments.
"""
import re
import difflib
from collections import namedtuple

from jedi._compatibility import use_metaclass
from jedi import settings
from jedi.common import splitlines
from jedi.parser import ParserWithRecovery
from jedi.parser.tree import EndMarker
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
    if _ends_with_newline(last_leaf):
        return last_leaf.start_pos[0]
    else:
        return last_leaf.end_pos[0]


def _ends_with_newline(leaf, suffix=''):
    if leaf.type == 'error_leaf':
        typ = leaf.original_type
    else:
        typ = leaf.type

    return typ == 'newline' or suffix.endswith('\n')


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


class _PositionUpdatingFinished(Exception):
    pass


def _update_positions(nodes, line_offset, last_leaf):
    for node in nodes:
        try:
            children = node.children
        except AttributeError:
            # Is a leaf
            node.line += line_offset
            if node is last_leaf:
                raise _PositionUpdatingFinished
        else:
            _update_positions(children, line_offset, last_leaf)


class DiffParser(object):
    def __init__(self, parser):
        self._parser = parser
        self._grammar = self._parser._grammar
        self._module = parser.get_root_node()

    def _reset(self):
        self._copy_count = 0
        self._parser_count = 0

        self._copied_ranges = []
        self._new_used_names = {}
        self._nodes_stack = _NodesStack(self._module)

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

        Returns the new module node.
        '''
        debug.speed('diff parser start')
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
        opcodes = sm.get_opcodes()
        debug.speed('diff parser calculated')
        debug.dbg('diff: line_lengths old: %s, new: %s' % (len(lines_old), line_length))

        if len(opcodes) == 1 and opcodes[0][0] == 'equal':
            self._copy_count = 1
            return self._module

        for operation, i1, i2, j1, j2 in opcodes:
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

        # With this action all change will finally be applied and we have a
        # changed module.
        self._nodes_stack.close()

        self._cleanup()
        if self._added_newline:
            self._parser.remove_last_newline()

        self._parser.source = ''.join(lines_new)

        # Good for debugging.
        if debug.debug_function:
            self._enable_debugging(lines_old, lines_new)
        last_pos = self._module.end_pos[0]
        if last_pos != line_length:
            current_lines = splitlines(self._module.get_code(), keepends=True)
            diff = difflib.unified_diff(current_lines, lines_new)
            raise Exception(
                "There's an issue (%s != %s) with the diff parser. Please report:\n%s"
                % (last_pos, line_length, ''.join(diff))
            )

        debug.speed('diff parser end')
        return self._module

    def _enable_debugging(self, lines_old, lines_new):
        if self._module.get_code() != ''.join(lines_new):
            debug.warning('parser issue:\n%s\n%s', repr(''.join(lines_old)),
                          repr(''.join(lines_new)))

    def _copy_from_old_parser(self, line_offset, until_line_old, until_line_new):
        copied_nodes = [None]

        while until_line_new > self._nodes_stack.parsed_until_line:
            parsed_until_line_old = self._nodes_stack.parsed_until_line - line_offset
            line_stmt = self._get_old_line_stmt(parsed_until_line_old + 1)
            if line_stmt is None:
                # Parse 1 line at least. We don't need more, because we just
                # want to get into a state where the old parser has statements
                # again that can be copied (e.g. not lines within parentheses).
                self._parse(self._nodes_stack.parsed_until_line + 1)
            elif not copied_nodes:
                # We have copied as much as possible (but definitely not too
                # much). Therefore we just parse the rest.
                # We might not reach the end, because there's a statement
                # that is not finished.
                self._parse(until_line_new)
            else:
                p_children = line_stmt.parent.children
                index = p_children.index(line_stmt)

                copied_nodes = self._nodes_stack.copy_nodes(
                    p_children[index:],
                    until_line_old,
                    line_offset
                )
                # Match all the nodes that are in the wanted range.
                if copied_nodes:
                    self._copy_count += 1

                    from_ = copied_nodes[0].get_start_pos_of_prefix()[0] + line_offset
                    to = self._nodes_stack.parsed_until_line
                    self._copied_ranges.append((from_, to))

                    debug.dbg('diff actually copy %s to %s', from_, to)

    def _get_old_line_stmt(self, old_line):
        leaf = self._module.get_leaf_for_position((old_line, 0), include_prefixes=True)

        if _ends_with_newline(leaf):
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

    def _get_before_insertion_node(self):
        if self._nodes_stack.is_empty():
            return None

        line = self._nodes_stack.parsed_until_line + 1
        node = self._new_module.last_leaf()
        while True:
            parent = node.parent
            if parent.type in ('suite', 'file_input'):
                assert node.end_pos[0] <= line
                assert node.end_pos[1] == 0 or '\n' in self._prefix
                return node
            node = parent

    def _parse(self, until_line):
        """
        Parses at least until the given line, but might just parse more until a
        valid state is reached.
        """
        while until_line > self._nodes_stack.parsed_until_line:
            node = self._try_parse_part(until_line)
            nodes = self._get_children_nodes(node)
            #self._insert_nodes(nodes)

            self._nodes_stack.add_parsed_nodes(nodes)
            debug.dbg(
                'parse part %s to %s (to %s in parser)',
                nodes[0].get_start_pos_of_prefix()[0],
                self._nodes_stack.parsed_until_line,
                node.end_pos[0] - 1
            )
            _merge_used_names(
                self._new_used_names,
                node.used_names
            )

    def _get_children_nodes(self, node):
        nodes = node.children
        first_element = nodes[0]
        # TODO this looks very strange...
        if first_element.type == 'error_leaf' and \
                first_element.original_type == 'indent':
            assert False, str(nodes)

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
        parsed_until_line = self._nodes_stack.parsed_until_line
        lines_after = self._parser_lines_new[parsed_until_line:]
        #print('parse_content', parsed_until_line, lines_after, until_line)
        tokenizer = self._diff_tokenize(
            lines_after,
            until_line,
            line_offset=parsed_until_line
        )
        self._active_parser = ParserWithRecovery(
            self._grammar,
            source='\n',
            start_parsing=False
        )
        return self._active_parser.parse(tokenizer=tokenizer)

    def _cleanup(self):
        """Add the used names from the old parser to the new one."""
        copied_line_numbers = set()
        for l1, l2 in self._copied_ranges:
            copied_line_numbers.update(range(l1, l2 + 1))

        new_used_names = self._new_used_names
        for key, names in self._module.used_names.items():
            for name in names:
                if name.line in copied_line_numbers:
                    new_used_names.setdefault(key, []).append(name)
        self._module.used_names = new_used_names

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


class _NodesStackNode(object):
    ChildrenGroup = namedtuple('ChildrenGroup', 'children line_offset last_line_offset_leaf')

    def __init__(self, tree_node, parent=None):
        self.tree_node = tree_node
        self.children_groups = []
        self.parent = parent

    def close(self):
        children = []
        for children_part, line_offset, last_line_offset_leaf in self.children_groups:
            if line_offset != 0:
                try:
                    _update_positions(
                        children_part, line_offset, last_line_offset_leaf)
                except _PositionUpdatingFinished:
                    pass
            children += children_part
        self.tree_node.children = children
        # Reset the parents
        for node in children:
            node.parent = self.tree_node

    def add(self, children, line_offset=0, last_line_offset_leaf=None):
        group = self.ChildrenGroup(children, line_offset, last_line_offset_leaf)
        self.children_groups.append(group)

    def get_last_line(self, suffix):
        if not self.children_groups:
            assert not self.parent
            return 0

        last_leaf = self.children_groups[-1].children[-1].last_leaf()
        line = last_leaf.end_pos[0]

        # Calculate the line offsets
        line += self.children_groups[-1].line_offset

        # Newlines end on the next line, which means that they would cover
        # the next line. That line is not fully parsed at this point.
        if _ends_with_newline(last_leaf, suffix):
            line -= 1
        line += suffix.count('\n')
        return line


class _NodesStack(object):
    endmarker_type = 'endmarker'

    def __init__(self, module):
        # Top of stack
        self._tos = self._base_node = _NodesStackNode(module)
        self._module = module
        self._last_prefix = ''
        self.prefix = ''

    def is_empty(self):
        return not self._base_node.children

    @property
    def parsed_until_line(self, ):
        return self._tos.get_last_line(self.prefix)

    def _get_insertion_node(self, indentation_node):
        indentation = indentation_node.start_pos[1]

        # find insertion node
        node = self._tos
        while True:
            tree_node = node.tree_node
            if tree_node.type == 'suite':
                # A suite starts with NEWLINE, ...
                node_indentation = tree_node.children[1].start_pos[1]

                if indentation >= node_indentation:  # Not a Dedent
                    # We might be at the most outer layer: modules. We
                    # don't want to depend on the first statement
                    # having the right indentation.
                    return node

            elif tree_node.type == 'file_input':
                return node

            node = self._close_tos()

    def _close_tos(self):
        self._tos.close()
        self._tos = self._tos.parent
        return self._tos

    def add_parsed_nodes(self, tree_nodes):
        tree_nodes = self._remove_endmarker(tree_nodes)
        if not tree_nodes:
            return

        assert tree_nodes[0].type != 'newline'

        node = self._get_insertion_node(tree_nodes[0])
        assert node.tree_node.type in ('suite', 'file_input')
        node.add(tree_nodes)
        self._update_tos(tree_nodes[-1])

    def _remove_endmarker(self, tree_nodes):
        """
        Helps cleaning up the tree nodes that get inserted.
        """
        last_leaf = tree_nodes[-1].last_leaf()
        is_endmarker = last_leaf.type == self.endmarker_type
        self._last_prefix = ''
        if is_endmarker:
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

        first_leaf = tree_nodes[0].first_leaf()
        first_leaf.prefix = self.prefix + first_leaf.prefix
        self.prefix = ''

        if is_endmarker:
            self.prefix = last_leaf.prefix

            tree_nodes = tree_nodes[:-1]

        return tree_nodes

    def copy_nodes(self, tree_nodes, until_line, line_offset):
        """
        Copies tree nodes from the old parser tree.

        Returns the number of tree nodes that were copied.
        """
        tos = self._get_insertion_node(tree_nodes[0])

        new_nodes, self._tos = self._copy_nodes(tos, tree_nodes, until_line, line_offset)
        return new_nodes

    def _copy_nodes(self, tos, nodes, until_line, line_offset):
        new_nodes = []

        new_tos = tos
        for node in nodes:
            if node.type == 'endmarker':
                # Endmarkers just distort all the checks below. Remove them.
                break

            if node.start_pos[0] > until_line:
                break
            # TODO this check might take a bit of time for large files. We
            # might want to change this to do more intelligent guessing or
            # binary search.
            if _get_last_line(node) > until_line:
                # We can split up functions and classes later.
                if node.type in ('classdef', 'funcdef') and node.children[-1].type == 'suite':
                    new_nodes.append(node)
                break

            new_nodes.append(node)

        if not new_nodes:
            return [], tos

        last_node = new_nodes[-1]
        line_offset_index = -1
        if last_node.type in ('classdef', 'funcdef'):
            suite = last_node.children[-1]
            if suite.type == 'suite':
                suite_tos = _NodesStackNode(suite)
                # Don't need to pass line_offset here, it's already done by the
                # parent.
                suite_nodes, recursive_tos = self._copy_nodes(
                    suite_tos, suite.children, until_line, line_offset)
                if len(suite_nodes) < 2:
                    # A suite only with newline is not valid.
                    new_nodes.pop()
                else:
                    suite_tos.parent = tos
                    new_tos = recursive_tos
                    line_offset_index = -2

        elif (new_nodes[-1].type in ('error_leaf', 'error_node') or
                          _is_flow_node(new_nodes[-1])):
            # Error leafs/nodes don't have a defined start/end. Error
            # nodes might not end with a newline (e.g. if there's an
            # open `(`). Therefore ignore all of them unless they are
            # succeeded with valid parser state.
            # If we copy flows at the end, they might be continued
            # after the copy limit (in the new parser).
            # In this while loop we try to remove until we find a newline.
            new_nodes.pop()
            while new_nodes:
                last_node = new_nodes[-1]
                if last_node.last_leaf().type == 'newline':
                    break
                new_nodes.pop()

        if new_nodes:
            try:
                last_line_offset_leaf = new_nodes[line_offset_index].last_leaf()
            except IndexError:
                line_offset = 0
                # In this case we don't have to calculate an offset, because
                # there's no children to be managed.
                last_line_offset_leaf = None
            tos.add(new_nodes, line_offset, last_line_offset_leaf)
        return new_nodes, new_tos

    def _update_tos(self, tree_node):
        if tree_node.type in ('suite', 'file_input'):
            self._tos = _NodesStackNode(tree_node, self._tos)
            self._tos.add(list(tree_node.children))
            self._update_tos(tree_node.children[-1])
        elif tree_node.type in ('classdef', 'funcdef'):
            self._update_tos(tree_node.children[-1])

    def close(self):
        while self._tos is not None:
            self._close_tos()

        # Add an endmarker.
        try:
            last_leaf = self._module.last_leaf()
            end_pos = list(last_leaf.end_pos)
        except IndexError:
            end_pos = [1, 0]
        lines = splitlines(self.prefix)
        assert len(lines) > 0
        if len(lines) == 1:
            end_pos[1] += len(lines[0])
        else:
            end_pos[0] += len(lines) - 1
            end_pos[1] = len(lines[-1])

        endmarker = EndMarker('', tuple(end_pos), self.prefix + self._last_prefix)
        endmarker.parent = self._module
        self._module.children.append(endmarker)
