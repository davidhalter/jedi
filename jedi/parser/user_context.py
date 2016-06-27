import re
import os
from collections import namedtuple

from jedi import cache
from jedi.parser import ParserWithRecovery
from jedi.parser.fast import FastParser

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
        pass

    def module(self):
        return self._parser().module
