import re
import operator
from functools import reduce

import common
import parsing
from _compatibility import use_metaclass

parser_cache = {}


class Module(parsing.Simple, parsing.Module):
    def __init__(self, parsers):
        super(Module, self).__init__((1,0))
        self.parsers = parsers
        self._end_pos = None, None
        self.reset_caches()

    def reset_caches(self):
        """ This module does a whole lot of caching, because it uses different
        parsers. """
        self.cache = {}

    def _get(self, name, operation, *args, **kwargs):
        key = (name, args, frozenset(kwargs.items()))
        if key not in self.cache:
            objs = (getattr(p.module, name)(*args, **kwargs) for p in self.parsers)
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
                                                        *args, **kwargs)
        elif name in properties:
            return self._get(name, properties[name])
        else:
            raise AttributeError("__getattr__ doesn't offer %s" % name)

    def get_statement_for_position(self, pos):
        key = 'get_statement_for_position', pos
        if key not in self.cache:
            for p in self.parsers:
                s = p.module.get_statement_for_position(self)
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
    def end_pos(self):
        return self._end_pos

    @end_pos.setter
    def end_pos(self, value):
        if None not in value and self._end_pos < value:
            self._end_pos = value

    def __repr__(self):
        return "<%s: %s@%s-%s>" % (type(self).__name__, self.name,
                                    self.start_pos[0], self.end_pos[0])


class CachedFastParser(type):
    """ This is a metaclass for caching `FastParser`. """
    def __call__(self, code, module_path=None, user_position=None):
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
                    self._user_scope = p.user_scope
                    break

        if isinstance(self._user_scope, parsing.SubModule):
            self._user_scope = self.module
        return self._user_scope

    @property
    def user_stmt(self):
        if self._user_stmt is None:
            for p in self.parsers:
                if p.user_stmt:
                    self._user_stmt = p.user_stmt
        return self._user_stmt

    def update(self, code, user_position=None):
        self.user_position = user_position
        self.reset_caches()
        self.parsers = []
        self.module.parsers = self.parsers

        self._parse(code)

    def _parse(self, code):
        """ :type code: str """
        r = r'(?:\n(?:def|class|@.*?\n(?:def|class))|^).*?(?=\n(?:def|class|@)|$)'
        parts = re.findall(r, code, re.DOTALL)

        line_offset = 0
        for p in parts:
            lines = p.count('\n')
            p = parsing.PyFuzzyParser(p, self.module_path, self.user_position,
                                line_offset=line_offset, stop_on_scope=True,
                                top_module=self.module)

            p.module.parent = self.module
            line_offset += lines
            self.parsers.append(p)

    def reset_caches(self):
        self._user_scope = None
        self._user_stmt = None
        self.module.reset_caches()
