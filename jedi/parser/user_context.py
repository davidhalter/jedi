import re
import os
from collections import namedtuple

from jedi import cache
from jedi.parser import ParserWithRecovery
from jedi.parser.fast import FastParser
from jedi.parser import tree

# TODO this should be part of the tokenizer not just of this user_context.
Token = namedtuple('Token', ['type', 'string', 'start_pos', 'prefix'])

REPLACE_STR = r"[bBuU]?[rR]?" + (r"(?:(')[^\n'\\]*(?:\\.[^\n'\\]*)*(?:'|$)" +
                                 '|' +
                                 r'(")[^\n"\\]*(?:\\.[^\n"\\]*)*(?:"|$))')
REPLACE_STR = re.compile(REPLACE_STR)


class UserContextParser(object):
    def __init__(self, grammar, source, path, position,
                 parser_done_callback, use_fast_parser=True):
        self._grammar = grammar
        self._source = source
        self._path = path and os.path.abspath(path)
        self._position = position
        self._use_fast_parser = use_fast_parser
        self._parser_done_callback = parser_done_callback

    @cache.underscore_memoization
    def _parser(self):
        cache.invalidate_star_import_cache(self._path)
        if self._use_fast_parser:
            parser = FastParser(self._grammar, self._source, self._path)
            # Don't pickle that module, because the main module is changing quickly
            cache.save_parser(self._path, parser, pickling=False)
        else:
            parser = ParserWithRecovery(self._grammar, self._source, self._path)
        self._parser_done_callback(parser)
        return parser

    @cache.underscore_memoization
    def user_scope(self):
        """
        Returns the scope in which the user resides. This includes flows.
        """
        user_stmt = self.module().get_statement_for_position(self._position)
        if user_stmt is None:
            def scan(scope):
                for s in scope.children:
                    if s.start_pos <= self._position <= s.end_pos:
                        if isinstance(s, (tree.Scope, tree.Flow)):
                            return scan(s) or s
                        elif s.type in ('suite', 'decorated'):
                            return scan(s)
                return None

            return scan(self.module()) or self.module()
        else:
            return user_stmt.get_parent_scope(include_flows=True)

    def module(self):
        return self._parser().module
