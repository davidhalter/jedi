"""
Basically a parser that is faster, because it tries to parse only parts and if
anything changes, it only reparses the changed parts. But because it's not
finished (and still not working as I want), I won't document it any further.
"""
import re
import operator

from _compatibility import use_metaclass, reduce, property
import settings
import parsing
import parsing_representation as pr
import cache
import common


SCOPE_CONTENTS = ['asserts', 'subscopes', 'imports', 'statements', 'returns']


class Module(pr.Simple, pr.Module):
    def __init__(self, parsers):
        self._end_pos = None, None
        super(Module, self).__init__(self, (1, 0))
        self.parsers = parsers
        self.reset_caches()

    def reset_caches(self):
        """ This module does a whole lot of caching, because it uses different
        parsers. """
        self.cache = {}
        for p in self.parsers:
            p.user_scope = None
            p.user_stmt = None

    def _get(self, name, operation, execute=False, *args, **kwargs):
        key = (name, args, frozenset(kwargs.items()))
        if key not in self.cache:
            if execute:
                objs = (getattr(p.module, name)(*args, **kwargs)
                                                    for p in self.parsers)
            else:
                objs = (getattr(p.module, name) for p in self.parsers)
            self.cache[key] = reduce(operation, objs)
        return self.cache[key]

    def __getattr__(self, name):
        if name == 'global_vars':
            return self._get(name, operator.add)
        elif name.startswith('__'):
            raise AttributeError('Not available!')
        else:
            return getattr(self.parsers[0].module, name)

    @property
    def used_names(self):
        if not self.parsers:
            raise NotImplementedError("Parser doesn't exist.")
        key = 'used_names'
        if key not in self.cache:
            dct = {}
            for p in self.parsers:
                for k, statement_set in p.module.used_names.items():
                    if k in dct:
                        dct[k] |= statement_set
                    else:
                        dct[k] = set(statement_set)

            self.cache[key] = dct
        return self.cache[key]

    @property
    def start_pos(self):
        """ overwrite start_pos of Simple """
        return 1, 0

    @start_pos.setter
    def start_pos(self):
        """ ignore """
        raise AttributeError('TODO remove - just a check if everything works fine.')

    @property
    def end_pos(self):
        return self._end_pos

    @end_pos.setter
    def end_pos(self, value):
        if None in self._end_pos \
                or None not in value and self._end_pos < value:
            self._end_pos = value

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
        self.parser = parser
        self.code = code
        self.hash = hash(code)

        self.children = []
        self._old_children = []
        # must be created before new things are added to it.
        try:
            # with fast_parser we have either 1 subscope or only statements.
            self._content_scope = self.parser.module.subscopes[0]
        except IndexError:
            self._content_scope = self.parser.module
        self.save_contents()

    def save_contents(self):
        scope = self._content_scope
        self._contents = {}
        for c in SCOPE_CONTENTS:
            self._contents[c] = getattr(scope, c)
        self._is_generator = scope.is_generator

    def reset_contents(self):
        scope = self._content_scope
        for key, c in self._contents.items():
            setattr(scope, key, c)
        scope.is_generator = self._is_generator

        for c in self.children:
            c.reset_contents()

    def parent_until_indent(self, indent):
        if self.indent >= indent and self.parent:
            self._old_children = []
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
                el = module.imports[0]
        return el.start_pos[1]

    def _set_items(self, parser, set_parent=False):
        # insert parser objects into current structure
        scope = self._content_scope
        for c in SCOPE_CONTENTS:
            content = getattr(scope, c)
            items = getattr(parser.module, c)
            if set_parent:
                for i in items:
                    i.parent = scope
            content += items
        scope.is_generator |= parser.module.is_generator

    def add_node(self, node):
        """Adding a node means adding a node that was already added earlier"""
        self.children.append(node)
        self._set_items(node.parser)
        node._old_children = node.children
        node.children = []
        return node

    def add_parser(self, parser, code):
        node = ParserNode(parser, code, self)
        self._set_items(parser, set_parent=True)
        self.children.append(node)
        return node


class FastParser(use_metaclass(CachedFastParser)):
    def __init__(self, code, module_path=None, user_position=None):
        # set values like `pr.Module`.
        self.module_path = module_path
        self.user_position = user_position

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
                    if self._user_scope is not None and not \
                            isinstance(self._user_scope, pr.SubModule):
                        continue
                    self._user_scope = p.user_scope

        if isinstance(self._user_scope, pr.SubModule):
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

    def scan_user_scope(self, sub_module):
        """ Scan with self.user_position.
        :type sub_module: pr.SubModule
        """
        for scope in sub_module.statements + sub_module.subscopes:
            if isinstance(scope, pr.Scope):
                if scope.start_pos <= self.user_position <= scope.end_pos:
                    return self.scan_user_scope(scope) or scope
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
                parts.append(txt)
                current_lines[:] = []

        r_keyword = '^[ \t]*(def|class|@|%s)' % '|'.join(common.FLOWS)

        lines = code.splitlines()
        current_lines = []
        parts = []
        is_decorator = False
        current_indent = 0
        new_indent = False
        in_flow = False
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
                if not in_flow:
                    add_part()
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
                        current_lines = []
                    is_decorator = '@' == m.group(1)
                    if not is_decorator:
                        current_indent += 1  # it must be higher
                        new_indent = True

            current_lines.append(l)
        add_part()

        for p in parts:
            #print '#####################################'
            #print p
            #print len(p.splitlines())
            pass

        return parts

    def _parse(self, code):
        """ :type code: str """
        parts = self._split_parts(code)
        self.parsers[:] = []

        self._code = code
        self._line_offset = 0
        self._start = 0
        p = None
        is_first = True
        for code_part in parts:
            lines = code_part.count('\n') + 1
            if is_first or self._line_offset >= p.end_pos[0] - 1:
                indent = len(re.match(r'[ \t]*', code_part).group(0))
                if is_first and self.current_node is not None:
                    nodes = [self.current_node]
                else:
                    nodes = []
                if self.current_node is not None:

                    self.current_node = \
                                self.current_node.parent_until_indent(indent)
                    nodes += self.current_node._old_children

                # check if code_part has already been parsed
                p, node = self._get_parser(code_part, nodes)

                if is_first:
                    if self.current_node is None:
                        self.current_node = ParserNode(p, code)
                    else:
                        self.current_node.parser = p
                        self.current_node.save_contents()
                else:
                    if node is None:
                        self.current_node = \
                                    self.current_node.add_parser(p, code)
                    else:
                        self.current_node = self.current_node.add_node(node)
                self.parsers.append(p)

                is_first = False

            self._line_offset += lines
            self._start += len(code_part) + 1  # +1 for newline

        #print(self.parsers[0].module.get_code())
        #for p in self.parsers:
        #    print(p.module.get_code())
        #    print(p.module.start_pos, p.module.end_pos)
        #exit()
        del self._code

    def _get_parser(self, code, nodes):
        h = hash(code)
        hashes = [n.hash for n in nodes]
        node = None
        try:
            index = hashes.index(h)
            if nodes[index].code != code:
                raise ValueError()
        except ValueError:
            p = parsing.Parser(self._code[self._start:],
                               self.module_path, self.user_position,
                               offset=(self._line_offset, 0),
                               is_fast_parser=True, top_module=self.module)
        else:
            node = nodes.pop(index)
            p = node.parser
            m = p.module
            m.line_offset += self._line_offset + 1 - m.start_pos[0]
            if self.user_position is not None and \
                    m.start_pos <= self.user_position <= m.end_pos:
                # It's important to take care of the whole user
                # positioning stuff, if no reparsing is being done.
                p.user_stmt = m.get_statement_for_position(
                            self.user_position, include_imports=True)
                if p.user_stmt:
                    p.user_scope = p.user_stmt.parent
                else:
                    p.user_scope = self.scan_user_scope(m) or self.module
        return p, node

    def reset_caches(self):
        self._user_scope = None
        self._user_stmt = None
        self.module.reset_caches()
        if self.current_node is not None:
            self.current_node.reset_contents()
