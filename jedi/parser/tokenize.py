# -*- coding: utf-8 -*-
"""
This tokenizer has been copied from the ``tokenize.py`` standard library
tokenizer. The reason was simple: The standanrd library  tokenizer fails
if the indentation is not right. The fast parser of jedi however requires
"wrong" indentation.

Basically this is a stripped down version of the standard library module, so
you can read the documentation there.
"""
from __future__ import absolute_import

import string
import re
from io import StringIO
from token import (tok_name, N_TOKENS, ENDMARKER, STRING, NUMBER, NAME, OP,
                   ERRORTOKEN, NEWLINE)

from jedi._compatibility import u, unicode

cookie_re = re.compile("coding[:=]\s*([-\w.]+)")


# From here on we have custom stuff (everything before was originally Python
# internal code).
FLOWS = ['if', 'else', 'elif', 'while', 'with', 'try', 'except', 'finally']


namechars = string.ascii_letters + '_'


COMMENT = N_TOKENS
tok_name[COMMENT] = 'COMMENT'
ENCODING = N_TOKENS + 1
tok_name[ENCODING] = 'ENCODING'


class TokenInfo(object):
    """
    The token object is an efficient representation of the structure
    (type, token, (start_pos_line, start_pos_col)). It has indexer
    methods that maintain compatibility to existing code that expects the above
    structure.

    >>> tuple(TokenInfo(1, 'foo' ,(3,4)))
    (1, 'foo', (3, 4), (3, 7))
    >>> repr(TokenInfo(1, "test", (1, 1)))
    "<TokenInfo: (1, 'test', (1, 1))>"
    >>> TokenInfo(1, 'bar', (3, 4)).__getstate__()
    (1, 'bar', 3, 4)
    >>> a = TokenInfo(0, 'baz', (0, 0))
    >>> a.__setstate__((1, 'foo', 3, 4))
    >>> a
    <TokenInfo: (1, 'foo', (3, 4))>
    >>> a.start_pos
    (3, 4)
    >>> a.string
    'foo'
    >>> a._start_pos_col
    4
    >>> TokenInfo(1, u("😷"), (1 ,1)).string + "p" == u("😷p")
    True
    """
    __slots__ = ("type", "string", "_start_pos_line", "_start_pos_col")

    def __init__(self, type, string, start_pos):
        self.type = type
        self.string = string
        self._start_pos_line = start_pos[0]
        self._start_pos_col = start_pos[1]

    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, tuple(self)[:3])

    # Backward compatibility
    def __getitem__(self, key):
        # Builds the same structure as tuple used to have
        if key == 0:
            return self.type
        elif key == 1:
            return self.string
        elif key == 2:
            return (self._start_pos_line, self._start_pos_col)
        elif key == 3:
            return self.end
        else:
            raise IndexError("list index out of range")

    @property
    def start_pos(self):
        return (self._start_pos_line, self._start_pos_col)

    @property
    def start(self):
        return (self._start_pos_line, self._start_pos_col)

    @property
    def end(self):
        """Returns end position respecting multiline tokens."""
        end_pos_line = self._start_pos_line
        lines = self.string.split('\n')
        if self.string.endswith('\n'):
            lines = lines[:-1]
            lines[-1] += '\n'
        end_pos_line += len(lines) - 1
        end_pos_col = self._start_pos_col
        # Check for multiline token
        if self._start_pos_line == end_pos_line:
            end_pos_col += len(lines[-1])
        else:
            end_pos_col = len(lines[-1])
        return (end_pos_line, end_pos_col)

    # Make cache footprint smaller for faster unpickling
    def __getstate__(self):
        return (
            self.type,
            self.string,
            self._start_pos_line,
            self._start_pos_col,
        )

    def __setstate__(self, state):
        self.type = state[0]
        self.string = state[1]
        self._start_pos_line = state[2]
        self._start_pos_col = state[3]


def group(*choices):
    return '(' + '|'.join(choices) + ')'


def any(*choices):
    return group(*choices) + '*'


def maybe(*choices):
    return group(*choices) + '?'


# Note: we use unicode matching for names ("\w") but ascii matching for
# number literals.
Whitespace = r'[ \f\t]*'
Comment = r'#[^\r\n]*'
Ignore = Whitespace + any(r'\\\r?\n' + Whitespace) + maybe(Comment)
Name = r'\w+'

Hexnumber = r'0[xX][0-9a-fA-F]+'
Binnumber = r'0[bB][01]+'
Octnumber = r'0[oO][0-7]+'
Decnumber = r'(?:0+|[1-9][0-9]*)'
Intnumber = group(Hexnumber, Binnumber, Octnumber, Decnumber)
Exponent = r'[eE][-+]?[0-9]+'
Pointfloat = group(r'[0-9]+\.[0-9]*', r'\.[0-9]+') + maybe(Exponent)
Expfloat = r'[0-9]+' + Exponent
Floatnumber = group(Pointfloat, Expfloat)
Imagnumber = group(r'[0-9]+[jJ]', Floatnumber + r'[jJ]')
Number = group(Imagnumber, Floatnumber, Intnumber)

# Tail end of ' string.
Single = r"[^'\\]*(?:\\.[^'\\]*)*'"
# Tail end of " string.
Double = r'[^"\\]*(?:\\.[^"\\]*)*"'
# Tail end of ''' string.
Single3 = r"[^'\\]*(?:(?:\\.|'(?!''))[^'\\]*)*'''"
# Tail end of """ string.
Double3 = r'[^"\\]*(?:(?:\\.|"(?!""))[^"\\]*)*"""'
Triple = group("[bB]?[rR]?'''", '[bB]?[rR]?"""')
# Single-line ' or " string.
String = group(r"[bB]?[rR]?'[^\n'\\]*(?:\\.[^\n'\\]*)*'",
               r'[bB]?[rR]?"[^\n"\\]*(?:\\.[^\n"\\]*)*"')

# Because of leftmost-then-longest match semantics, be sure to put the
# longest operators first (e.g., if = came before ==, == would get
# recognized as two instances of =).
Operator = group(r"\*\*=?", r">>=?", r"<<=?", r"!=",
                 r"//=?", r"->",
                 r"[+\-*/%&|^=<>]=?",
                 r"~")

Bracket = '[][(){}]'
Special = group(r'\r?\n', r'\.\.\.', r'[:;.,@]')
Funny = group(Operator, Bracket, Special)

PlainToken = group(Number, Funny, String, Name)
Token = Ignore + PlainToken

# First (or only) line of ' or " string.
ContStr = group(r"[bB]?[rR]?'[^\n'\\]*(?:\\.[^\n'\\]*)*" +
                group("'", r'\\\r?\n'),
                r'[bB]?[rR]?"[^\n"\\]*(?:\\.[^\n"\\]*)*' +
                group('"', r'\\\r?\n'))
PseudoExtras = group(r'\\\r?\n', Comment, Triple)
PseudoToken = Whitespace + group(PseudoExtras, Number, Funny, ContStr, Name)


def _compile(expr):
    return re.compile(expr, re.UNICODE)


tokenprog, pseudoprog, single3prog, double3prog = map(
    _compile, (Token, PseudoToken, Single3, Double3))
endprogs = {"'": _compile(Single), '"': _compile(Double),
            "'''": single3prog, '"""': double3prog,
            "r'''": single3prog, 'r"""': double3prog,
            "b'''": single3prog, 'b"""': double3prog,
            "br'''": single3prog, 'br"""': double3prog,
            "R'''": single3prog, 'R"""': double3prog,
            "B'''": single3prog, 'B"""': double3prog,
            "bR'''": single3prog, 'bR"""': double3prog,
            "Br'''": single3prog, 'Br"""': double3prog,
            "BR'''": single3prog, 'BR"""': double3prog,
            'r': None, 'R': None, 'b': None, 'B': None}

triple_quoted = {}
for t in ("'''", '"""',
          "r'''", 'r"""', "R'''", 'R"""',
          "b'''", 'b"""', "B'''", 'B"""',
          "br'''", 'br"""', "Br'''", 'Br"""',
          "bR'''", 'bR"""', "BR'''", 'BR"""'):
    triple_quoted[t] = t
single_quoted = {}
for t in ("'", '"',
          "r'", 'r"', "R'", 'R"',
          "b'", 'b"', "B'", 'B"',
          "br'", 'br"', "Br'", 'Br"',
          "bR'", 'bR"', "BR'", 'BR"'):
    single_quoted[t] = t

del _compile

tabsize = 8


def source_tokens(source, line_offset=0):
    """Generate tokens from a the source code (string)."""
    source = source + '\n'  # end with \n, because the parser needs it
    readline = StringIO(source).readline
    return generate_tokens(readline, line_offset)


def generate_tokens(readline, line_offset=0):
    """
    The original stdlib Python version with minor modifications.
    Modified to not care about dedents.
    """
    lnum = line_offset
    numchars = '0123456789'
    contstr = ''
    contline = None
    while True:             # loop over lines in stream
        line = readline()  # readline returns empty if it's finished. See StringIO
        if not line:
            if contstr:
                yield TokenInfo(ERRORTOKEN, contstr, contstr_start)
            break

        lnum += 1
        pos, max = 0, len(line)

        if contstr:                                         # continued string
            endmatch = endprog.match(line)
            if endmatch:
                pos = endmatch.end(0)
                yield TokenInfo(STRING, contstr + line[:pos], contstr_start)
                contstr = ''
                contline = None
            else:
                contstr = contstr + line
                contline = contline + line
                continue

        while pos < max:
            pseudomatch = pseudoprog.match(line, pos)
            if not pseudomatch:                             # scan for tokens
                yield TokenInfo(ERRORTOKEN, line[pos], (lnum, pos))
                pos += 1
                continue

            start, pos = pseudomatch.span(1)
            spos = (lnum, start)
            token, initial = line[start:pos], line[start]

            if (initial in numchars or                      # ordinary number
                    (initial == '.' and token != '.' and token != '...')):
                yield TokenInfo(NUMBER, token, spos)
            elif initial in '\r\n':
                yield TokenInfo(NEWLINE, token, spos)
            elif initial == '#':
                assert not token.endswith("\n")
                yield TokenInfo(COMMENT, token, spos)
            elif token in triple_quoted:
                endprog = endprogs[token]
                endmatch = endprog.match(line, pos)
                if endmatch:                                # all on one line
                    pos = endmatch.end(0)
                    token = line[start:pos]
                    yield TokenInfo(STRING, token, spos)
                else:
                    contstr_start = (lnum, start)                # multiple lines
                    contstr = line[start:]
                    contline = line
                    break
            elif initial in single_quoted or \
                    token[:2] in single_quoted or \
                    token[:3] in single_quoted:
                if token[-1] == '\n':                       # continued string
                    contstr_start = lnum, start
                    endprog = (endprogs[initial] or endprogs[token[1]] or
                               endprogs[token[2]])
                    contstr = line[start:]
                    contline = line
                    break
                else:                                       # ordinary string
                    yield TokenInfo(STRING, token, spos)
            elif initial in namechars:                      # ordinary name
                yield TokenInfo(NAME, token, spos)
            elif initial == '\\' and line[start:] == '\\\n':  # continued stmt
                continue
            else:
                yield TokenInfo(OP, token, spos)

    yield TokenInfo(ENDMARKER, '', (lnum, 0))
