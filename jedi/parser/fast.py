"""
Basically a parser that is faster, because it tries to parse only parts and if
anything changes, it only reparses the changed parts. But because it's not
finished (and still not working as I want), I won't document it any further.
"""
import re
from itertools import chain

from jedi._compatibility import use_metaclass, unicode
from jedi import settings
from jedi import common
from jedi.parser import Parser
from jedi.parser import tree as pr
from jedi.parser import tokenize
from jedi import cache
from jedi.parser.tokenize import (source_tokens, FLOWS, NEWLINE, COMMENT,
                                  ENDMARKER, INDENT, DEDENT)


class FastModule(pr.Module, pr.Simple):
    type = 'file_input'

    def __init__(self, parsers):
        super(FastModule, self).__init__([])
        self.parsers = parsers
        self.reset_caches()

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
        """
        used_names = {}
        for p in self.parsers:
            for k, statement_set in p.module.used_names.items():
                if k in used_names:
                    used_names[k] |= statement_set
                else:
                    used_names[k] = set(statement_set)
        """
        return MergedNamesDict([p.module.used_names for p in self.parsers])

    def __repr__(self):
        return "<fast.%s: %s@%s-%s>" % (type(self).__name__, self.name,
                                        self.start_pos[0], self.end_pos[0])


class MergedNamesDict(object):
    def __init__(self, dicts):
        self._dicts = dicts

    def __getitem__(self, value):
        print(value, self._dicts)
        return list(chain.from_iterable(dct.get(value, []) for dct in self._dicts))

    def values(self):
        lst = []
        for dct in self._dicts:
            lst.append(dct.values())
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
    def __init__(self, fast_module, parser, code, parent=None):
        self._fast_module = fast_module
        self.parent = parent

        self.parser_children = []
        # must be created before new things are added to it.
        self.save_contents(parser, code)

    def save_contents(self, parser, code):
        print('SAVE')
        self.code = code
        self.hash = hash(code)
        self.parser = parser

        try:
            # With fast_parser we have either 1 subscope or only statements.
            self._content_scope = self._names_dict_scope = parser.module.subscopes[0]
        except IndexError:
            self._content_scope = self._fast_module
            self._names_dict_scope = parser.module

        """
        scope = self._content_scope
        self._contents = {}
        for c in pr.SCOPE_CONTENTS:
            self._contents[c] = list(getattr(scope, c))
        self._is_generator = scope.is_generator
        """

        self.old_children = self.parser_children
        self.parser_children = []

    def reset_contents(self):
        """
        scope = self._content_scope
        for key, c in self._contents.items():
            setattr(scope, key, list(c))
        scope.is_generator = self._is_generator
        """

        """
        if self.parent is None:
            # Global vars of the first one can be deleted, in the global scope
            # they make no sense.
            self.parser.module.global_vars = []
        """

        for c in self.parser_children:
            c.reset_contents()

    def close(self):
        """
        Closes the current parser node. This means that after this no further
        nodes should be added anymore.
        """
        print('CLOSE NODE', self.parent, self.parser_children)
        print(self.parser.module.names_dict, [p.parser.module.names_dict for p in
        self.parser_children])
        # We only need to replace the dict if multiple dictionaries are used:
        if self.parser_children:
            dcts = [n.parser.module.names_dict for n in self.parser_children]
            dct = MergedNamesDict([self._names_dict_scope.names_dict] + dcts)
            self._content_scope.names_dict = dct

    def parent_until_indent(self, indent=None):
        if indent is None or self.indent >= indent and self.parent:
            self.old_children = []
            if self.parent is not None:
                self.close()
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
        scope = self._content_scope
        if set_parent:
            for child in parser.module.children:
                child.parent = scope
                scope.children.append(child)
                print('\t\t', scope, child)
                """
                if isinstance(i, (pr.Function, pr.Class)):
                    for d in i.decorators:
                        d.parent = scope
                """
        # TODO global_vars ? is_generator ?
        """
        cur = self
        while cur.parent is not None:
            cur = cur.parent
        cur.parser.module.global_vars += parser.module.global_vars

        scope.is_generator |= parser.module.is_generator
        """

    def add_node(self, node, set_parent=False):
        """Adding a node means adding a node that was already added earlier"""
        print('ADD')
        self.parser_children.append(node)
        self._set_items(node.parser, set_parent=set_parent)
        node.old_children = node.parser_children  # TODO potential memory leak?
        node.parser_children = []

        """
        scope = self.content_scope
        while scope is not None:
            #print('x',scope)
            if not isinstance(scope, pr.SubModule):
                # TODO This seems like a strange thing. Check again.
                scope.end_pos = node.content_scope.end_pos
            scope = scope.parent
        """
        return node

    def add_parser(self, parser, code):
        print('add parser')
        return self.add_node(ParserNode(self._fast_module, parser, code, self), True)


class FastParser(use_metaclass(CachedFastParser)):

    _keyword_re = re.compile('^[ \t]*(def|class|@|%s)' % '|'.join(tokenize.FLOWS))

    def __init__(self, grammar, code, module_path=None):
        # set values like `pr.Module`.
        self._grammar = grammar
        self.module_path = module_path
        print(module_path)

        self.current_node = None
        self.parsers = []
        self.module = FastModule(self.parsers)
        self.reset_caches()

        try:
            self._parse(code)
        except:
            # FastParser is cached, be careful with exceptions
            del self.parsers[:]
            raise

    def update(self, code):
        self.reset_caches()

        try:
            self._parse(code)
        except:
            # FastParser is cached, be careful with exceptions
            del self.parsers[:]
            raise

    def _split_parts(self, code):
        """
        Split the code into different parts. This makes it possible to parse
        each part seperately and therefore cache parts of the file and not
        everything.
        """
        def gen_part():
            text = '\n'.join(current_lines)
            del current_lines[:]
            return text

        # Split only new lines. Distinction between \r\n is the tokenizer's
        # job.
        self._lines = code.split('\n')
        current_lines = []
        is_decorator = False
        current_indent = 0
        old_indent = 0
        new_indent = False
        in_flow = False
        # All things within flows are simply being ignored.
        for l in self._lines:
            # check for dedents
            s = l.lstrip('\t ')
            indent = len(l) - len(s)
            if not s or s[0] in ('#', '\r'):
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
                    in_flow = m.group(1) in tokenize.FLOWS
                    if not is_decorator and not in_flow:
                        if current_lines:
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

    def _parse(self, code):
        """ :type code: str """
        def empty_parser():
            new, temp = self._get_parser(unicode(''), unicode(''), 0, [], False)
            return new

        del self.parsers[:]

        line_offset = 0
        start = 0
        p = None
        is_first = True
        for code_part in self._split_parts(code):
            if is_first or line_offset + 1 == p.module.end_pos[0]:
                print(repr(code_part))
                indent = len(code_part) - len(code_part.lstrip('\t '))
                if is_first and self.current_node is not None:
                    nodes = [self.current_node]
                else:
                    nodes = []
                if self.current_node is not None:
                    self.current_node = self.current_node.parent_until_indent(indent)
                    nodes += self.current_node.old_children

                # check if code_part has already been parsed
                # print '#'*45,line_offset, p and p.module.end_pos, '\n', code_part
                p, node = self._get_parser(code_part, code[start:],
                                           line_offset, nodes, not is_first)
                print('HmmmmA', p.module.names_dict)

                # The actual used code_part is different from the given code
                # part, because of docstrings for example there's a chance that
                # splits are wrong.
                used_lines = self._lines[line_offset:p.module.end_pos[0]]
                code_part_actually_used = '\n'.join(used_lines)

                if is_first and p.module.subscopes:
                    print('NOXXXX')
                    # special case, we cannot use a function subscope as a
                    # base scope, subscopes would save all the other contents
                    new = empty_parser()
                    if self.current_node is None:
                        self.current_node = ParserNode(self.module, new, '')
                    else:
                        self.current_node.save_contents(new, '')
                    self.parsers.append(new)
                    is_first = False

                if is_first:
                    if self.current_node is None:
                        self.current_node = ParserNode(self.module, p, code_part_actually_used)
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

            line_offset += code_part.count('\n') + 1
            start += len(code_part) + 1  # +1 for newline

        if self.parsers:
            self.current_node = self.current_node.parent_until_indent()
            self.current_node.close()
        else:
            self.parsers.append(empty_parser())

        """ TODO used?
        self.module.end_pos = self.parsers[-1].module.end_pos
        """

        # print(self.parsers[0].module.get_code())

    def _get_parser(self, code, parser_code, line_offset, nodes, no_docstr):
        h = hash(code)
        for index, node in enumerate(nodes):
            if node.hash == h and node.code == code:
                if node != self.current_node:
                    offset = int(nodes[0] == self.current_node)
                    self.current_node.old_children.pop(index - offset)
                p = node.parser
                m = p.module
                m.line_offset += line_offset + 1 - m.start_pos[0]
                break
        else:
            tokenizer = FastTokenizer(parser_code, line_offset)
            p = Parser(self._grammar, parser_code, self.module_path, tokenizer=tokenizer)
            #p.module.parent = self.module  # With the new parser this is not
                                            # necessary anymore?
            node = None

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
        self._gen = source_tokens(source, line_offset)
        self._closed = False

        # fast parser options
        self.current = self.previous = None, '', (0, 0)
        self._in_flow = False
        self._new_indent = False
        self._parser_indent = self._old_parser_indent = 0
        self._is_decorator = False
        self._first_stmt = True
        self._parentheses_level = 0
        self._indent_counter = 0
        self._returned_endmarker = False

    def __iter__(self):
        print('NEW')
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

        self.previous = self.current
        self.current = current

        # this is exactly the same check as in fast_parser, but this time with
        # tokenize and therefore precise.
        breaks = ['def', 'class', '@']

        if typ == INDENT:
            self._indent_counter += 1
        elif typ == DEDENT:
            self._indent_counter -= 1
            return current

        # Check for NEWLINE with a valid token here, which symbolizes the
        # indent.
        # Ignore comments/newlines, irrelevant for indentation.
        if self.previous[0] in (None, NEWLINE, DEDENT) \
                and typ not in (COMMENT, NEWLINE):
            # print c, tok_name[c[0]]
            indent = start_pos[1]
            if self._parentheses_level:
                # parentheses ignore the indentation rules.
                pass
            elif indent < self._parser_indent:  # -> dedent
                self._parser_indent = indent
                self._new_indent = False
                if not self._in_flow or indent < self._old_parser_indent:
                    return self._close()

                self._in_flow = False
            elif self._new_indent:
                self._parser_indent = indent
                self._new_indent = False

            if not self._in_flow:
                if value in FLOWS or value in breaks:
                    self._in_flow = value in FLOWS
                    if not self._is_decorator and not self._in_flow:
                        return self._close()

                    self._is_decorator = '@' == value
                    if not self._is_decorator:
                        self._old_parser_indent = self._parser_indent
                        self._parser_indent += 1  # new scope: must be higher
                        self._new_indent = True

            if value != '@':
                if self._first_stmt and not self._new_indent:
                    self._parser_indent = indent
                self._first_stmt = False

        # Ignore closing parentheses, because they are all
        # irrelevant for the indentation.

        if value in '([{' and value:
            self._parentheses_level += 1
        elif value in ')]}' and value:
            self._parentheses_level = max(self._parentheses_level - 1, 0)
        return current

    def _close(self):
        if self._first_stmt:
            # Continue like nothing has happened, because we want to enter
            # the first class/function.
            self._first_stmt = True
            print('NOOO', self.current)
            return self.current
        else:
            self._closed = True
            return self._finish_dedents()

    def _finish_dedents(self):
        start_pos = self.current[2]
        print('FINISH', self._indent_counter)
        if self._indent_counter:
            self._indent_counter -= 1
            return tokenize.DEDENT, '', start_pos, ''
        elif not self._returned_endmarker:
            self._returned_endmarker = True
            return tokenize.ENDMARKER, '', start_pos, ''
        else:
            raise StopIteration
