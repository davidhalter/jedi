"""
Basically a parser that is faster, because it tries to parse only parts and if
anything changes, it only reparses the changed parts. But because it's not
finished (and still not working as I want), I won't document it any further.
"""
import re

from jedi._compatibility import use_metaclass, unicode
from jedi import settings
from jedi import common
from jedi.parser import Parser
from jedi.parser import representation as pr
from jedi.parser import tokenize
from jedi import cache
from jedi.parser.tokenize import (source_tokens, Token, FLOWS, NEWLINE,
                                  COMMENT, ENDMARKER)


class Module(pr.Simple, pr.Module):
    def __init__(self, parsers):
        super(Module, self).__init__(self, (1, 0))
        self.parsers = parsers
        self.reset_caches()

        self.start_pos = 1, 0
        self.end_pos = None, None

    def reset_caches(self):
        """ This module does a whole lot of caching, because it uses different
        parsers. """
        with common.ignored(AttributeError):
            del self._used_names

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError('Not available!')
        else:
            return getattr(self.parsers[0].module, name)

    @property
    @cache.underscore_memoization
    def used_names(self):
        used_names = {}
        for p in self.parsers:
            for k, statement_set in p.module.used_names.items():
                if k in used_names:
                    used_names[k] |= statement_set
                else:
                    used_names[k] = set(statement_set)
        return used_names

    def __repr__(self):
        return "<fast.%s: %s@%s-%s>" % (type(self).__name__, self.name,
                                        self.start_pos[0], self.end_pos[0])


class CachedFastParser(type):
    """ This is a metaclass for caching `FastParser`. """
    def __call__(self, source, module_path=None):
        if not settings.fast_parser:
            return Parser(source, module_path)

        pi = cache.parser_cache.get(module_path, None)
        if pi is None or isinstance(pi.parser, Parser):
            p = super(CachedFastParser, self).__call__(source, module_path)
        else:
            p = pi.parser  # pi is a `cache.ParserCacheItem`
            p.update(source)
        return p


class ParserNode(object):
    def __init__(self, parser, code, parent=None):
        self.parent = parent

        self.children = []
        # must be created before new things are added to it.
        self.save_contents(parser, code)

    def save_contents(self, parser, code):
        self.code = code
        self.hash = hash(code)
        self.parser = parser

        try:
            # with fast_parser we have either 1 subscope or only statements.
            self.content_scope = parser.module.subscopes[0]
        except IndexError:
            self.content_scope = parser.module

        scope = self.content_scope
        self._contents = {}
        for c in pr.SCOPE_CONTENTS:
            self._contents[c] = list(getattr(scope, c))
        self._is_generator = scope.is_generator

        self.old_children = self.children
        self.children = []

    def reset_contents(self):
        scope = self.content_scope
        for key, c in self._contents.items():
            setattr(scope, key, list(c))
        scope.is_generator = self._is_generator

        if self.parent is None:
            # Global vars of the first one can be deleted, in the global scope
            # they make no sense.
            self.parser.module.global_vars = []

        for c in self.children:
            c.reset_contents()

    def parent_until_indent(self, indent=None):
        if indent is None or self.indent >= indent and self.parent:
            self.old_children = []
            if self.parent is not None:
                return self.parent.parent_until_indent(indent)
        return self

    @property
    def indent(self):
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
                        return self.parent.indent + 1
        return el.start_pos[1]

    def _set_items(self, parser, set_parent=False):
        # insert parser objects into current structure
        scope = self.content_scope
        for c in pr.SCOPE_CONTENTS:
            content = getattr(scope, c)
            items = getattr(parser.module, c)
            if set_parent:
                for i in items:
                    if i is None:
                        continue  # happens with empty returns
                    i.parent = scope.use_as_parent
                    if isinstance(i, (pr.Function, pr.Class)):
                        for d in i.decorators:
                            d.parent = scope.use_as_parent
            content += items

        # global_vars
        cur = self
        while cur.parent is not None:
            cur = cur.parent
        cur.parser.module.global_vars += parser.module.global_vars

        scope.is_generator |= parser.module.is_generator

    def add_node(self, node, set_parent=False):
        """Adding a node means adding a node that was already added earlier"""
        self.children.append(node)
        self._set_items(node.parser, set_parent=set_parent)
        node.old_children = node.children  # TODO potential memory leak?
        node.children = []

        scope = self.content_scope
        while scope is not None:
            #print('x',scope)
            if not isinstance(scope, pr.SubModule):
                # TODO This seems like a strange thing. Check again.
                scope.end_pos = node.content_scope.end_pos
            scope = scope.parent
        return node

    def add_parser(self, parser, code):
        return self.add_node(ParserNode(parser, code, self), True)


class FastParser(use_metaclass(CachedFastParser)):
    def __init__(self, code, module_path=None):
        # set values like `pr.Module`.
        self.module_path = module_path

        self.current_node = None
        self.parsers = []
        self.module = Module(self.parsers)
        self.reset_caches()

        try:
            self._parse(code)
        except:
            # FastParser is cached, be careful with exceptions
            self.parsers[:] = []
            raise

    def update(self, code):
        self.reset_caches()

        try:
            self._parse(code)
        except:
            # FastParser is cached, be careful with exceptions
            self.parsers[:] = []
            raise

    def _split_parts(self, code):
        """
        Split the code into different parts. This makes it possible to parse
        each part seperately and therefore cache parts of the file and not
        everything.
        """
        def add_part():
            txt = '\n'.join(current_lines)
            if txt:
                if add_to_last and parts:
                    parts[-1] += '\n' + txt
                else:
                    parts.append(txt)
                current_lines[:] = []

        r_keyword = '^[ \t]*(def|class|@|%s)' % '|'.join(tokenize.FLOWS)

        # Split only new lines. Distinction between \r\n is the tokenizer's
        # job.
        self._lines = code.split('\n')
        current_lines = []
        parts = []
        is_decorator = False
        current_indent = 0
        old_indent = 0
        new_indent = False
        in_flow = False
        add_to_last = False
        # All things within flows are simply being ignored.
        for i, l in enumerate(self._lines):
            # check for dedents
            m = re.match('^([\t ]*)(.?)', l)
            indent = len(m.group(1))
            if m.group(2) in ['', '#']:
                current_lines.append(l)  # just ignore comments and blank lines
                continue

            if indent < current_indent:  # -> dedent
                current_indent = indent
                new_indent = False
                if not in_flow or indent < old_indent:
                    add_part()
                    add_to_last = False
                in_flow = False
            elif new_indent:
                current_indent = indent
                new_indent = False

            # Check lines for functions/classes and split the code there.
            if not in_flow:
                m = re.match(r_keyword, l)
                if m:
                    in_flow = m.group(1) in tokenize.FLOWS
                    if not is_decorator and not in_flow:
                        add_part()
                        add_to_last = False
                    is_decorator = '@' == m.group(1)
                    if not is_decorator:
                        old_indent = current_indent
                        current_indent += 1  # it must be higher
                        new_indent = True
                elif is_decorator:
                    is_decorator = False
                    add_to_last = True

            current_lines.append(l)
        add_part()

        return parts

    def _parse(self, code):
        """ :type code: str """
        def empty_parser():
            new, temp = self._get_parser(unicode(''), unicode(''), 0, [], False)
            return new

        parts = self._split_parts(code)
        self.parsers[:] = []

        line_offset = 0
        start = 0
        p = None
        is_first = True

        for code_part in parts:
            lines = code_part.count('\n') + 1
            if is_first or line_offset >= p.module.end_pos[0]:
                indent = len(re.match(r'[ \t]*', code_part).group(0))
                if is_first and self.current_node is not None:
                    nodes = [self.current_node]
                else:
                    nodes = []
                if self.current_node is not None:

                    self.current_node = \
                        self.current_node.parent_until_indent(indent)
                    nodes += self.current_node.old_children

                # check if code_part has already been parsed
                # print '#'*45,line_offset, p and p.module.end_pos, '\n', code_part
                p, node = self._get_parser(code_part, code[start:],
                                           line_offset, nodes, not is_first)

                # The actual used code_part is different from the given code
                # part, because of docstrings for example there's a chance that
                # splits are wrong.
                used_lines = self._lines[line_offset:p.module.end_pos[0]]
                code_part_actually_used = '\n'.join(used_lines)

                if is_first and p.module.subscopes:
                    # special case, we cannot use a function subscope as a
                    # base scope, subscopes would save all the other contents
                    new = empty_parser()
                    if self.current_node is None:
                        self.current_node = ParserNode(new, '')
                    else:
                        self.current_node.save_contents(new, '')
                    self.parsers.append(new)
                    is_first = False

                if is_first:
                    if self.current_node is None:
                        self.current_node = ParserNode(p, code_part_actually_used)
                    else:
                        self.current_node.save_contents(p, code_part_actually_used)
                else:
                    if node is None:
                        self.current_node = \
                            self.current_node.add_parser(p, code_part_actually_used)
                    else:
                        self.current_node = self.current_node.add_node(node)

                self.parsers.append(p)

                is_first = False
            #else:
                #print '#'*45, line_offset, p.module.end_pos, 'theheck\n', repr(code_part)

            line_offset += lines
            start += len(code_part) + 1  # +1 for newline

        if self.parsers:
            self.current_node = self.current_node.parent_until_indent()
        else:
            self.parsers.append(empty_parser())

        self.module.end_pos = self.parsers[-1].module.end_pos

        # print(self.parsers[0].module.get_code())
        del code

    def _get_parser(self, code, parser_code, line_offset, nodes, no_docstr):
        h = hash(code)
        hashes = [n.hash for n in nodes]
        node = None
        try:
            index = hashes.index(h)
            if nodes[index].code != code:
                raise ValueError()
        except ValueError:
            tokenizer = FastTokenizer(parser_code, line_offset)
            p = Parser(parser_code, self.module_path, tokenizer=tokenizer,
                       top_module=self.module, no_docstr=no_docstr)
            p.module.parent = self.module
        else:
            if nodes[index] != self.current_node:
                offset = int(nodes[0] == self.current_node)
                self.current_node.old_children.pop(index - offset)
            node = nodes.pop(index)
            p = node.parser
            m = p.module
            m.line_offset += line_offset + 1 - m.start_pos[0]

        return p, node

    def reset_caches(self):
        self.module.reset_caches()
        if self.current_node is not None:
            self.current_node.reset_contents()


class FastTokenizer(object):
    """
    Breaks when certain conditions are met, i.e. a new function or class opens.
    """
    def __init__(self, source, line_offset=0):
        self.source = source
        self.gen = source_tokens(source, line_offset)
        self.closed = False

        # fast parser options
        self.current = self.previous = Token(None, '', (0, 0))
        self.in_flow = False
        self.new_indent = False
        self.parser_indent = self.old_parser_indent = 0
        self.is_decorator = False
        self.first_stmt = True

    def next(self):
        """ Python 2 Compatibility """
        return self.__next__()

    def __next__(self):
        if self.closed:
            raise common.MultiLevelStopIteration()

        current = next(self.gen)
        tok_type = current.type
        tok_str = current.string
        if tok_type == ENDMARKER:
            raise common.MultiLevelStopIteration()

        self.previous = self.current
        self.current = current

        # this is exactly the same check as in fast_parser, but this time with
        # tokenize and therefore precise.
        breaks = ['def', 'class', '@']

        def close():
            if not self.first_stmt:
                self.closed = True
                raise common.MultiLevelStopIteration()

        # ignore comments/ newlines
        if self.previous.type in (None, NEWLINE) and tok_type not in (COMMENT, NEWLINE):
            # print c, tok_name[c[0]]
            indent = current.start_pos[1]
            if indent < self.parser_indent:  # -> dedent
                self.parser_indent = indent
                self.new_indent = False
                if not self.in_flow or indent < self.old_parser_indent:
                    close()
                self.in_flow = False
            elif self.new_indent:
                self.parser_indent = indent
                self.new_indent = False

            if not self.in_flow:
                if tok_str in FLOWS or tok_str in breaks:
                    self.in_flow = tok_str in FLOWS
                    if not self.is_decorator and not self.in_flow:
                        close()
                    self.is_decorator = '@' == tok_str
                    if not self.is_decorator:
                        self.old_parser_indent = self.parser_indent
                        self.parser_indent += 1  # new scope: must be higher
                        self.new_indent = True

            if tok_str != '@':
                if self.first_stmt and not self.new_indent:
                    self.parser_indent = indent
                self.first_stmt = False
        return current
