"""
Basically a parser that is faster, because it tries to parse only parts and if
anything changes, it only reparses the changed parts. But because it's not
finished (and still not working as I want), I won't document it any further.
"""
import re

from jedi._compatibility import use_metaclass
from jedi import settings
from jedi import parsing
from jedi import parsing_representation as pr
from jedi import cache
from jedi import common


SCOPE_CONTENTS = ['asserts', 'subscopes', 'imports', 'statements', 'returns']


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
        self._used_names = None
        for p in self.parsers:
            p.user_scope = None
            p.user_stmt = None

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError('Not available!')
        else:
            return getattr(self.parsers[0].module, name)

    @property
    def used_names(self):
        if self._used_names is None:
            dct = {}
            for p in self.parsers:
                for k, statement_set in p.module.used_names.items():
                    if k in dct:
                        dct[k] |= statement_set
                    else:
                        dct[k] = set(statement_set)

            self._used_names = dct
        return self._used_names

    def __repr__(self):
        return "<%s: %s@%s-%s>" % (type(self).__name__, self.name,
                                    self.start_pos[0], self.end_pos[0])


class CachedFastParser(type):
    """ This is a metaclass for caching `FastParser`. """
    def __call__(self, source, module_path=None, user_position=None):
        if not settings.fast_parser:
            return parsing.Parser(source, module_path, user_position)

        pi = cache.parser_cache.get(module_path, None)
        if pi is None or isinstance(pi.parser, parsing.Parser):
            p = super(CachedFastParser, self).__call__(source, module_path,
                                                            user_position)
        else:
            p = pi.parser  # pi is a `cache.ParserCacheItem`
            p.update(source, user_position)
        return p


class ParserNode(object):
    def __init__(self, parser, code, parent=None):
        self.parent = parent
        self.code = code
        self.hash = hash(code)

        self.children = []
        # must be created before new things are added to it.
        self.save_contents(parser)

    def save_contents(self, parser):
        self.parser = parser

        try:
            # with fast_parser we have either 1 subscope or only statements.
            self.content_scope = parser.module.subscopes[0]
        except IndexError:
            self.content_scope = parser.module

        scope = self.content_scope
        self._contents = {}
        for c in SCOPE_CONTENTS:
            self._contents[c] = list(getattr(scope, c))
        self._is_generator = scope.is_generator

        self.old_children = self.children
        self.children = []

    def reset_contents(self):
        scope = self.content_scope
        for key, c in self._contents.items():
            setattr(scope, key, list(c))
        scope.is_generator = self._is_generator
        self.parser.user_scope = self.parser.module

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
        for c in SCOPE_CONTENTS:
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
        node.old_children = node.children
        node.children = []
        return node

    def add_parser(self, parser, code):
        return self.add_node(ParserNode(parser, code, self), True)


class FastParser(use_metaclass(CachedFastParser)):
    def __init__(self, code, module_path=None, user_position=None):
        # set values like `pr.Module`.
        self.module_path = module_path
        self.user_position = user_position
        self._user_scope = None

        self.current_node = None
        self.parsers = []
        self.module = Module(self.parsers)
        self.reset_caches()

        self._parse(code)

    @property
    def user_scope(self):
        if self._user_scope is None:
            for p in self.parsers:
                if p.user_scope:
                    if isinstance(p.user_scope, pr.SubModule):
                        continue
                    self._user_scope = p.user_scope

        if isinstance(self._user_scope, pr.SubModule) \
                    or self._user_scope is None:
            self._user_scope = self.module
        return self._user_scope

    @property
    def user_stmt(self):
        if self._user_stmt is None:
            for p in self.parsers:
                if p.user_stmt:
                    self._user_stmt = p.user_stmt
                    break
        return self._user_stmt

    def update(self, code, user_position=None):
        self.user_position = user_position
        self.reset_caches()

        self._parse(code)

    def _scan_user_scope(self, sub_module):
        """ Scan with self.user_position. """
        for scope in sub_module.statements + sub_module.subscopes:
            if isinstance(scope, pr.Scope):
                if scope.start_pos <= self.user_position <= scope.end_pos:
                    return self._scan_user_scope(scope) or scope
        return None

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

        r_keyword = '^[ \t]*(def|class|@|%s)' % '|'.join(common.FLOWS)

        lines = code.splitlines()
        current_lines = []
        parts = []
        is_decorator = False
        current_indent = 0
        old_indent = 0
        new_indent = False
        in_flow = False
        add_to_last = False
        # All things within flows are simply being ignored.
        for i, l in enumerate(lines):
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
                    in_flow = m.group(1) in common.FLOWS
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
            new, temp = self._get_parser('', '', 0, [], False)
            return new

        parts = self._split_parts(code)
        self.parsers[:] = []

        line_offset = 0
        start = 0
        p = None
        is_first = True

        for code_part in parts:
            lines = code_part.count('\n') + 1
            if is_first or line_offset >= p.end_pos[0]:
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
                #print '#'*45,line_offset, p and p.end_pos, '\n', code_part
                p, node = self._get_parser(code_part, code[start:],
                                           line_offset, nodes, not is_first)

                if is_first and p.module.subscopes:
                    # special case, we cannot use a function subscope as a
                    # base scope, subscopes would save all the other contents
                    new = empty_parser()
                    if self.current_node is None:
                        self.current_node = ParserNode(new, '')
                    else:
                        self.current_node.save_contents(new)
                    self.parsers.append(new)
                    is_first = False

                if is_first:
                    if self.current_node is None:
                        self.current_node = ParserNode(p, code_part)
                    else:
                        self.current_node.save_contents(p)
                else:
                    if node is None:
                        self.current_node = \
                                    self.current_node.add_parser(p, code_part)
                    else:
                        self.current_node = self.current_node.add_node(node)

                if self.current_node.parent and (isinstance(p.user_scope,
                                pr.SubModule) or p.user_scope is None) \
                        and self.user_position \
                        and p.start_pos <= self.user_position < p.end_pos:
                    p.user_scope = self.current_node.parent.content_scope

                self.parsers.append(p)

                is_first = False
            else:
                #print '#'*45, line_offset, p.end_pos, 'theheck\n', code_part 
                pass

            line_offset += lines
            start += len(code_part) + 1  # +1 for newline

        if self.parsers:
            self.current_node = self.current_node.parent_until_indent()
        else:
            self.parsers.append(empty_parser())

        self.module.end_pos = self.parsers[-1].end_pos

        #print(self.parsers[0].module.get_code())
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
            p = parsing.Parser(parser_code, self.module_path,
                               self.user_position, offset=(line_offset, 0),
                               is_fast_parser=True, top_module=self.module,
                               no_docstr=no_docstr)
            p.module.parent = self.module
        else:
            if nodes[index] != self.current_node:
                offset = int(nodes[0] == self.current_node)
                self.current_node.old_children.pop(index - offset)
            node = nodes.pop(index)
            p = node.parser
            m = p.module
            m.line_offset += line_offset + 1 - m.start_pos[0]
            if self.user_position is not None and \
                    m.start_pos[0] <= self.user_position[0] <= m.end_pos[0]:
                # It's important to take care of the whole user
                # positioning stuff, if no reparsing is being done.
                p.user_stmt = m.get_statement_for_position(
                            self.user_position, include_imports=True)
                if p.user_stmt:
                    p.user_scope = p.user_stmt.parent
                else:
                    p.user_scope = self._scan_user_scope(m) or m

        return p, node

    def reset_caches(self):
        self._user_scope = None
        self._user_stmt = None
        self.module.reset_caches()
        if self.current_node is not None:
            self.current_node.reset_contents()
