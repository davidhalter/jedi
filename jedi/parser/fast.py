"""
Basically a parser that is faster, because it tries to parse only parts and if
anything changes, it only reparses the changed parts. But because it's not
finished (and still not working as I want), I won't document it any further.
"""
import re
from itertools import chain

from jedi._compatibility import use_metaclass, unicode
from jedi import settings
from jedi.parser import Parser
from jedi.parser import tree as pr
from jedi.parser import tokenize
from jedi import cache
from jedi import debug
from jedi.parser.tokenize import (source_tokens, NEWLINE,
                                  ENDMARKER, INDENT, DEDENT)

FLOWS = ['if', 'else', 'elif', 'while', 'with', 'try', 'except', 'finally', 'for']


class FastModule(pr.SubModule):
    type = 'file_input'

    def __init__(self, module_path):
        super(FastModule, self).__init__([])
        self.modules = []
        self.reset_caches()
        self.names_dict = {}
        self.path = module_path

    def reset_caches(self):
        self.modules = []
        try:
            del self._used_names  # Remove the used names cache.
        except AttributeError:
            pass  # It was never used.

    @property
    @cache.underscore_memoization
    def used_names(self):
        return MergedNamesDict([m.used_names for m in self.modules])

    @property
    def global_names(self):
        return [name for m in self.modules for name in m.global_names]

    @property
    def error_statement_stacks(self):
        return [e for m in self.modules for e in m.error_statement_stacks]

    def __repr__(self):
        return "<fast.%s: %s@%s-%s>" % (type(self).__name__, self.name,
                                        self.start_pos[0], self.end_pos[0])

    # To avoid issues with with the `parser.Parser`, we need setters that do
    # nothing, because if pickle comes along and sets those values.
    @global_names.setter
    def global_names(self, value):
        pass

    @error_statement_stacks.setter
    def error_statement_stacks(self, value):
        pass

    @used_names.setter
    def used_names(self, value):
        pass



class MergedNamesDict(object):
    def __init__(self, dicts):
        self.dicts = dicts

    def __iter__(self):
        return iter(set(key for dct in self.dicts for key in dct))

    def __getitem__(self, value):
        return list(chain.from_iterable(dct.get(value, []) for dct in self.dicts))

    def items(self):
        dct = {}
        for d in self.dicts:
            for key, values in d.items():
                try:
                    dct_values = dct[key]
                    dct_values += values
                except KeyError:
                    dct[key] = list(values)
        return dct.items()

    def values(self):
        lst = []
        for dct in self.dicts:
            lst += dct.values()
        return lst


class CachedFastParser(type):
    """ This is a metaclass for caching `FastParser`. """
    def __call__(self, grammar, source, module_path=None):
        if not settings.fast_parser:
            return Parser(grammar, source, module_path)

        pi = cache.parser_cache.get(module_path, None)
        if pi is None or isinstance(pi.parser, Parser):
            p = super(CachedFastParser, self).__call__(grammar, source, module_path)
        else:
            p = pi.parser  # pi is a `cache.ParserCacheItem`
            p.update(source)
        return p


class ParserNode(object):
    def __init__(self, fast_module):
        self._fast_module = fast_module
        self.parent = None

        self._node_children = []
        self.source = None
        self.hash = None
        self.parser = None
        self._content_scope = self._fast_module

    def __repr__(self):
        module = self.parser.module
        try:
            return '<%s: %s-%s>' % (type(self).__name__, module.start_pos, module.end_pos)
        except IndexError:
            # There's no module yet.
            return '<%s: empty>' % type(self).__name__

    def set_parser(self, parser, source):
        self.source = source
        self.hash = hash(source)
        self.parser = parser

        try:
            # With fast_parser we have either 1 subscope or only statements.
            self._content_scope = parser.module.subscopes[0]
        except IndexError:
            self._content_scope = parser.module

        # We need to be able to reset the original children of a parser.
        self._old_children = list(self._content_scope.children)
        self._node_children = []

    def reset_node(self):
        """
        Removes changes that were applied in this class.
        """
        self._node_children = []
        scope = self._content_scope
        scope.children = list(self._old_children)
        try:
            # This works if it's a MergedNamesDict.
            # We are correcting it, because the MergedNamesDicts are artificial
            # and can change after closing a node.
            scope.names_dict = scope.names_dict.dicts[0]
        except AttributeError:
            pass

    def close(self):
        """
        Closes the current parser node. This means that after this no further
        nodes should be added anymore.
        """
        #print('CLOSE NODE', id(self), self.parent, self._node_children)
        # We only need to replace the dict if multiple dictionaries are used:
        if self._node_children:
            dcts = [n.parser.module.names_dict for n in self._node_children]
            # Need to insert the own node as well.
            dcts.insert(0, self._content_scope.names_dict)
            self._content_scope.names_dict = MergedNamesDict(dcts)

    def parent_until_indent(self, indent=None):
        if indent is None or self._indent >= indent and self.parent:
            if self.parent is not None:
                self.close()
                return self.parent.parent_until_indent(indent)
        return self

    @property
    def _indent(self):
        if not self.parent:
            return 0
        module = self.parser.module
        try:
            el = module.subscopes[0]
        except IndexError:
            try:
                el = module.statements[0]
            except IndexError:
                try:
                    el = module.imports[0]
                except IndexError:
                    try:
                        el = [r for r in module.returns if r is not None][0]
                    except IndexError:
                        el = module.children[0]
        return el.start_pos[1]

    def add_node(self, node, line_offset):
        """Adding a node means adding a node that was already added earlier"""
        # Changing the line offsets is very important, because if they don't
        # fit, all the start_pos values will be wrong.
        m = node.parser.module
        node.parser.position_modifier.line = line_offset
        self._fast_module.modules.append(m)
        node.parent = self

        self._node_children.append(node)

        # Insert parser objects into current structure. We only need to set the
        # parents and children in a good way.
        scope = self._content_scope
        for child in m.children:
            child.parent = scope
            scope.children.append(child)

        return node

    def all_sub_nodes(self):
        """
        Returns all nodes including nested ones.
        """
        for n in self._node_children:
            yield n
            for y in n.all_sub_nodes():
                yield y

    @cache.underscore_memoization  # Should only happen once!
    def remove_last_newline(self):
        self.parser.remove_last_newline()


class FastParser(use_metaclass(CachedFastParser)):

    _keyword_re = re.compile('^[ \t]*(def|class|@|%s)' % '|'.join(FLOWS))

    def __init__(self, grammar, source, module_path=None):
        # set values like `pr.Module`.
        self._grammar = grammar
        self.module_path = module_path
        self._reset_caches()
        self.update(source)

    def _reset_caches(self):
        self.module = FastModule(self.module_path)
        self.current_node = ParserNode(self.module)
        self.current_node.set_parser(self, '')

    def update(self, source):
        # For testing purposes: It is important that the number of parsers used
        # can be minimized. With this variable we can test it.
        self.number_parsers_used = 0
        self.number_of_splits = 0
        self.module.reset_caches()
        try:
            self._parse(source)
        except:
            # FastParser is cached, be careful with exceptions.
            self._reset_caches()
            raise

    def _split_parts(self, source):
        """
        Split the source code into different parts. This makes it possible to
        parse each part seperately and therefore cache parts of the file and
        not everything.
        """
        def gen_part():
            text = ''.join(current_lines)
            del current_lines[:]
            self.number_of_splits += 1
            return text

        def just_newlines(current_lines):
            for line in current_lines:
                line = line.lstrip('\t \n\r')
                if line and line[0] != '#':
                    return False
            return True

        # Split only new lines. Distinction between \r\n is the tokenizer's
        # job.
        self._lines = source.splitlines(True)
        current_lines = []
        is_decorator = False
        current_indent = 0
        old_indent = 0
        new_indent = False
        in_flow = False
        # All things within flows are simply being ignored.
        for i, l in enumerate(self._lines):
            # check for dedents
            s = l.lstrip('\t \n\r')
            indent = len(l) - len(s)
            if not s or s[0] == '#':
                current_lines.append(l)  # just ignore comments and blank lines
                continue

            if indent < current_indent:  # -> dedent
                current_indent = indent
                new_indent = False
                if not in_flow or indent < old_indent:
                    if current_lines:
                        yield gen_part()
                in_flow = False
            elif new_indent:
                current_indent = indent
                new_indent = False

            # Check lines for functions/classes and split the code there.
            if not in_flow:
                m = self._keyword_re.match(l)
                if m:
                    in_flow = m.group(1) in FLOWS
                    if not is_decorator and not in_flow:
                        if not just_newlines(current_lines):
                            yield gen_part()
                    is_decorator = '@' == m.group(1)
                    if not is_decorator:
                        old_indent = current_indent
                        current_indent += 1  # it must be higher
                        new_indent = True
                elif is_decorator:
                    is_decorator = False

            current_lines.append(l)
        if current_lines:
            yield gen_part()

    def _parse(self, source):
        """ :type source: str """
        added_newline = False
        if not source or source[-1] != '\n':
            # To be compatible with Pythons grammar, we need a newline at the
            # end. The parser would handle it, but since the fast parser abuses
            # the normal parser in various ways, we need to care for this
            # ourselves.
            source += '\n'
            added_newline = True

        line_offset = 0
        start = 0
        is_first = True
        nodes = list(self.current_node.all_sub_nodes())
        # Now we can reset the node, because we have all the old nodes.
        self.current_node.reset_node()

        for code_part in self._split_parts(source):
            # If the last code part parsed isn't equal to the current end_pos,
            # we know that the parser went further (`def` start in a
            # docstring). So just parse the next part.
            if is_first or line_offset + 1 == self.current_node.parser.module.end_pos[0]:
                indent = len(code_part) - len(code_part.lstrip('\t '))
                self.current_node = self.current_node.parent_until_indent(indent)

                # check if code_part has already been parsed
                self.current_node = self._get_node(code_part, source[start:],
                                                   line_offset, nodes, not is_first)
                is_first = False

            line_offset += code_part.count('\n')
            start += len(code_part)

        if added_newline:
            self.current_node.remove_last_newline()

        # Now that the for loop is finished, we still want to close all nodes.
        self.current_node = self.current_node.parent_until_indent()
        self.current_node.close()

        debug.dbg('Parsed %s, with %s parsers in %s splits.'
                  % (self.module_path, self.number_parsers_used,
                     self.number_of_splits))

        # print(self.parsers[0].module.get_code())

    def _get_node(self, source, parser_code, line_offset, nodes, no_docstr):
        """
        Side effect: Alters the list of nodes.
        """
        h = hash(source)
        for index, node in enumerate(nodes):
            #print('EQ', node, repr(node.source), repr(source))
            if node.hash == h and node.source == source:
                node.reset_node()
                nodes.remove(node)
                break
        else:
            tokenizer = FastTokenizer(parser_code, 0)
            self.number_parsers_used += 1
            #print('CODE', repr(source))
            p = Parser(self._grammar, parser_code, self.module_path, tokenizer=tokenizer)
            node = ParserNode(self.module)

            end = line_offset + p.module.end_pos[0]
            used_lines = self._lines[line_offset:end - 1]
            code_part_actually_used = ''.join(used_lines)
            node.set_parser(p, code_part_actually_used)

        self.current_node.add_node(node, line_offset)
        return node


class FastTokenizer(object):
    """
    Breaks when certain conditions are met, i.e. a new function or class opens.
    """
    def __init__(self, source, line_offset=0):
        # TODO remove the whole line_offset stuff, it's not used anymore.
        self.source = source
        self._gen = source_tokens(source, line_offset)
        self._closed = False

        # fast parser options
        self.current = self.previous = NEWLINE, '', (0, 0)
        self._in_flow = False
        self._is_decorator = False
        self._first_stmt = True
        self._parentheses_level = 0
        self._indent_counter = 0
        self._flow_indent_counter = 0
        self._returned_endmarker = False
        self._expect_indent = False

    def __iter__(self):
        return self

    def next(self):
        """ Python 2 Compatibility """
        return self.__next__()

    def __next__(self):
        if self._closed:
            return self._finish_dedents()

        typ, value, start_pos, prefix = current = next(self._gen)
        if typ == ENDMARKER:
            self._closed = True
            self._returned_endmarker = True
            return current

        self.previous = self.current
        self.current = current

        if typ == INDENT:
            self._indent_counter += 1
            if not self._expect_indent and not self._first_stmt:
                # This does not mean that there is an actual flow, but it means
                # that the INDENT is either syntactically wrong or a flow.
                self._in_flow = True
            self._expect_indent = False
        elif typ == DEDENT:
            self._indent_counter -= 1
            if self._in_flow and self._indent_counter == self._flow_indent_counter:
                self._in_flow = False
            elif not self._in_flow:
                self._closed = True
            return current

        # Parentheses ignore the indentation rules. The other three stand for
        # new lines.
        if self.previous[0] in (NEWLINE, INDENT, DEDENT) \
                and not self._parentheses_level and typ != INDENT:
            # Check for NEWLINE, which symbolizes the indent.
           # print('X', repr(value), tokenize.tok_name[typ])
            if not self._in_flow:
                self._in_flow = value in FLOWS
                if self._in_flow:
                    self._flow_indent_counter = self._indent_counter
                elif value in ('def', 'class', '@'):
                    # The values here are exactly the same check as in
                    # _split_parts, but this time with tokenize and therefore
                    # precise.
                    if not self._first_stmt and not self._is_decorator:
                        return self._close()

                    self._is_decorator = '@' == value
                    if not self._is_decorator:
                        self._first_stmt = False
                        self._expect_indent = True
                elif self._expect_indent:
                    return self._close()
                else:
                    self._first_stmt = False

        if value in '([{' and value:
            self._parentheses_level += 1
        elif value in ')]}' and value:
            # Ignore closing parentheses, because they are all
            # irrelevant for the indentation.
            self._parentheses_level = max(self._parentheses_level - 1, 0)
        return current

    def _close(self):
        if self._first_stmt:
            # Continue like nothing has happened, because we want to enter
            # the first class/function.
            if self.current[1] != '@':
                self._first_stmt = False
            return self.current
        else:
            self._closed = True
            return self._finish_dedents()

    def _finish_dedents(self):
        if self._indent_counter:
            self._indent_counter -= 1
            return DEDENT, '', self.current[2], ''
        elif not self._returned_endmarker:
            self._returned_endmarker = True
            # We're using the current prefix for the endmarker to not loose any
            # information. However we care about "lost" lines. The prefix of
            # the current line (indent) will always be included in the current
            # line.
            cur = self.current
            while cur[0] == DEDENT:
                cur = next(self._gen)
            prefix = cur[3]

            # \Z for the end of the string. $ is bugged, because it has the
            # same behavior with or without re.MULTILINE.
            prefix = re.sub(r'[^\n]+\Z', '', prefix)
            return ENDMARKER, '', self.current[2], prefix
        else:
            raise StopIteration
