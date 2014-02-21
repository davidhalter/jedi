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
from jedi._compatibility import StringIO
from token import *
import collections
cookie_re = re.compile("coding[:=]\s*([-\w.]+)")

from jedi import common

namechars = string.ascii_letters + '_'


COMMENT = N_TOKENS
tok_name[COMMENT] = 'COMMENT'
ENCODING = N_TOKENS + 2
tok_name[ENCODING] = 'ENCODING'
N_TOKENS += 3


class TokenInfo(collections.namedtuple('TokenInfo', 'type string start end')):
    def __repr__(self):
        annotated_type = '%d (%s)' % (self.type, tok_name[self.type])
        return ('TokenInfo(type=%s, string=%r, start=%r, end=%r, line=%r)' %
                self._replace(type=annotated_type))


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
    source = source + '\n'  # end with \n, because the parser needs it
    readline = StringIO(source).readline
    return generate_tokens(readline, line_offset)


def generate_tokens(readline, line_offset=0):
    """
    The original stdlib Python version with minor modifications.
    Modified to not care about dedents.
    """
    lnum = line_offset
    continued = False
    numchars = '0123456789'
    contstr = ''
    contline = None
    while True:             # loop over lines in stream
        line = readline()  # readline returns empty if it's finished. See StringIO
        if not line:
            if contstr:
                yield TokenInfo(ERRORTOKEN, contstr, strstart, (lnum, pos))
            break

        lnum += 1
        pos, max = 0, len(line)

        if contstr:                                         # continued string
            endmatch = endprog.match(line)
            if endmatch:
                pos = end = endmatch.end(0)
                yield TokenInfo(STRING, contstr + line[:end], strstart, (lnum, end))
                contstr = ''
                contline = None
            else:
                contstr = contstr + line
                contline = contline + line
                continue

        while pos < max:
            pseudomatch = pseudoprog.match(line, pos)
            if not pseudomatch:                             # scan for tokens
                yield TokenInfo(ERRORTOKEN, line[pos],
                               (lnum, pos), (lnum, pos + 1))
                pos += 1
                continue

            start, end = pseudomatch.span(1)
            spos, epos, pos = (lnum, start), (lnum, end), end
            token, initial = line[start:end], line[start]

            if (initial in numchars or                      # ordinary number
                    (initial == '.' and token != '.' and token != '...')):
                yield TokenInfo(NUMBER, token, spos, epos)
            elif initial in '\r\n':
                yield TokenInfo(NEWLINE, token, spos, epos)
            elif initial == '#':
                assert not token.endswith("\n")
                yield TokenInfo(COMMENT, token, spos, epos)
            elif token in triple_quoted:
                endprog = endprogs[token]
                endmatch = endprog.match(line, pos)
                if endmatch:                                # all on one line
                    pos = endmatch.end(0)
                    token = line[start:pos]
                    yield TokenInfo(STRING, token, spos, (lnum, pos))
                else:
                    strstart = (lnum, start)                # multiple lines
                    contstr = line[start:]
                    contline = line
                    break
            elif initial in single_quoted or \
                    token[:2] in single_quoted or \
                    token[:3] in single_quoted:
                if token[-1] == '\n':                       # continued string
                    strstart = (lnum, start)
                    endprog = (endprogs[initial] or endprogs[token[1]] or
                               endprogs[token[2]])
                    contstr = line[start:]
                    contline = line
                    break
                else:                                       # ordinary string
                    yield TokenInfo(STRING, token, spos, epos)
            elif initial in namechars:                      # ordinary name
                yield TokenInfo(NAME, token, spos, epos)
            elif initial == '\\' and line[start:] == '\\\n':  # continued stmt
                continue
            else:
                yield TokenInfo(OP, token, spos, epos)

    yield TokenInfo(ENDMARKER, '', (lnum, 0), (lnum, 0))


# From here on we have custom stuff (everything before was originally Python
# internal code).
FLOWS = ['if', 'else', 'elif', 'while', 'with', 'try', 'except', 'finally']


class NoErrorTokenizer(object):
    def __init__(self, source, line_offset=0, is_fast_parser=False):
        self.source = source
        self.gen = source_tokens(source, line_offset)
        self.closed = False

        # fast parser options
        self.is_fast_parser = is_fast_parser
        self.current = self.previous = [None, None, (0, 0), (0, 0), '']
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

        self.last_previous = self.previous
        self.previous = self.current
        self.current = next(self.gen)
        c = self.current

        if c[0] == ENDMARKER:
            self.current = self.previous
            self.previous = self.last_previous
            raise common.MultiLevelStopIteration()

        # this is exactly the same check as in fast_parser, but this time with
        # tokenize and therefore precise.
        breaks = ['def', 'class', '@']

        def close():
            if not self.first_stmt:
                self.closed = True
                raise common.MultiLevelStopIteration()
        # ignore comments/ newlines
        if self.is_fast_parser \
                and self.previous[0] in (None, NEWLINE) \
                and c[0] not in (COMMENT, NEWLINE):
            # print c, tok_name[c[0]]

            tok = c[1]
            indent = c[2][1]
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
                if tok in FLOWS or tok in breaks:
                    self.in_flow = tok in FLOWS
                    if not self.is_decorator and not self.in_flow:
                        close()
                    self.is_decorator = '@' == tok
                    if not self.is_decorator:
                        self.old_parser_indent = self.parser_indent
                        self.parser_indent += 1  # new scope: must be higher
                        self.new_indent = True

            if tok != '@':
                if self.first_stmt and not self.new_indent:
                    self.parser_indent = indent
                self.first_stmt = False
        return c
