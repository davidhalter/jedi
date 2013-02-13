import re
import operator

from _compatibility import use_metaclass, reduce, property
import settings
import parsing

parser_cache = {}


class Module(parsing.Simple, parsing.Module):
    def __init__(self, parsers):
        self._end_pos = None, None
        super(Module, self).__init__(self, (1,0))
        self.parsers = parsers
        self.reset_caches()
        self.line_offset = 0

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
        operators = {'get_imports': operator.add,
                     'get_code': operator.add,
                     'get_set_vars': operator.add,
                     'get_defined_names': operator.add,
                     'is_empty': operator.and_
                    }
        properties = {'subscopes': operator.add,
                      'imports': operator.add,
                      'statements': operator.add,
                      'imports': operator.add,
                      'asserts': operator.add,
                      'global_vars': operator.add
                     }
        if name in operators:
            return lambda *args, **kwargs: self._get(name, operators[name],
                                                        True, *args, **kwargs)
        elif name in properties:
            return self._get(name, properties[name])
        else:
            raise AttributeError("__getattr__ doesn't offer %s" % name)

    def get_statement_for_position(self, pos):
        key = 'get_statement_for_position', pos
        if key not in self.cache:
            for p in self.parsers:
                s = p.module.get_statement_for_position(pos)
                if s:
                    self.cache[key] = s
                    break
            else:
                self.cache[key] = None
        return self.cache[key]

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
    def docstr(self):
        if not self.parsers:
            raise NotImplementedError("Parser doesn't exist.")
        return self.parsers[0].module.docstr

    @property
    def name(self):
        if not self.parsers:
            raise NotImplementedError("Parser doesn't exist.")
        return self.parsers[0].module.name

    @property
    def path(self):
        if not self.parsers:
            raise NotImplementedError("Parser doesn't exist.")
        return self.parsers[0].module.path

    @property
    def is_builtin(self):
        if not self.parsers:
            raise NotImplementedError("Parser doesn't exist.")
        return self.parsers[0].module.is_builtin

    @property
    def start_pos(self):
        """ overwrite start_pos of Simple """
        return 1, 0

    @start_pos.setter
    def start_pos(self):
        """ ignore """
        pass

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
    def __call__(self, code, module_path=None, user_position=None):
        if not settings.fast_parser:
            return parsing.PyFuzzyParser(code, module_path, user_position)
        if module_path is None or module_path not in parser_cache:
            p = super(CachedFastParser, self).__call__(code, module_path,
                                                            user_position)
            parser_cache[module_path] = p
        else:
            p = parser_cache[module_path]
            p.update(code, user_position)
        return p


class FastParser(use_metaclass(CachedFastParser)):
    def __init__(self, code, module_path=None, user_position=None):
        # set values like `parsing.Module`.
        self.module_path = module_path
        self.user_position = user_position

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
                            isinstance(self._user_scope, parsing.SubModule):
                        continue
                    self._user_scope = p.user_scope

        if isinstance(self._user_scope, parsing.SubModule):
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
        :type sub_module: parsing.SubModule
        """
        for scope in sub_module.statements + sub_module.subscopes:
            if isinstance(scope, parsing.Scope):
                if scope.start_pos <= self.user_position <= scope.end_pos:
                    return self.scan_user_scope(scope) or scope
        return None

    def _parse(self, code):
        """ :type code: str """
        r = r'(?:\n(?:def|class|@.*?\n(?:def|class))|^).*?' \
            r'(?=\n(?:def|class|@)|$)'
        parts = re.findall(r, code, re.DOTALL)

        if len(parts) > 1 and not re.match('def|class|@', parts[0]):
            # Merge the first two because `common.NoErrorTokenizer` is not able
            # to know if there's a class/func or not.
            # Therefore every part has it's own class/func. Exactly one.
            parts[0] += parts[1]
            parts.pop(1)

        if settings.fast_parser_always_reparse:
            self.parsers[:] = []

        # dict comprehensions are not available in py2.5/2.6 :-(
        hashes = dict((p.hash, p) for p in self.parsers)

        line_offset = 0
        start = 0
        p = None
        parser_order = 0
        for code_part in parts:
            lines = code_part.count('\n')
            # the parser is using additional newlines, therefore substract
            if p is None or line_offset >= p.end_pos[0] - 2:
                # check if code_part has already been parsed
                h = hash(code_part)

                if h in hashes and hashes[h].code == code_part:
                    p = hashes[h]
                    del hashes[h]
                    m = p.module
                    m.line_offset += line_offset + 1 - m.start_pos[0]
                    if self.user_position is not None and \
                            m.start_pos <= self.user_position <= m.end_pos:
                        # It's important to take care of the whole user
                        # positioning stuff, if no reparsing is being done.
                        p.user_stmt = m.get_statement_for_position(
                                    self.user_position, include_imports=True)
                        if p.user_stmt:
                            p.user_scope = p.user_stmt.parent
                        else:
                            p.user_scope = self.scan_user_scope(m) \
                                            or self.module
                else:
                    p = parsing.PyFuzzyParser(code[start:],
                                self.module_path, self.user_position,
                                line_offset=line_offset, stop_on_scope=True,
                                top_module=self.module)

                    p.hash = h
                    p.code = code_part
                    p.module.parent = self.module
                self.parsers.insert(parser_order, p)

                parser_order += 1
            line_offset += lines
            start += len(code_part)
        self.parsers[parser_order + 1:] = []

    def reset_caches(self):
        self._user_scope = None
        self._user_stmt = None
        self.module.reset_caches()
