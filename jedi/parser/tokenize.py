# -*- coding: utf-8 -*-
"""
This tokenizer has been copied from the ``tokenize.py`` standard library
tokenizer. The reason was simple: The standard library tokenizer fails
if the indentation is not right. The fast parser of jedi however requires
"wrong" indentation.

Basically this is a stripped down version of the standard library module, so
you can read the documentation there. Additionally we included some speed and
memory optimizations here.
"""
from __future__ import absolute_import

import string
import re
from collections import namedtuple
import itertools as _itertools

from jedi.parser.token import (tok_name, N_TOKENS, ENDMARKER, STRING, NUMBER, opmap,
                               NAME, OP, ERRORTOKEN, NEWLINE, INDENT, DEDENT)
from jedi._compatibility import is_py3, py_version, u
from jedi.common import splitlines


cookie_re = re.compile("coding[:=]\s*([-\w.]+)")


if is_py3:
    # Python 3 has str.isidentifier() to check if a char is a valid identifier
    is_identifier = str.isidentifier
else:
    namechars = string.ascii_letters + '_'
    is_identifier = lambda s: s in namechars


COMMENT = N_TOKENS
tok_name[COMMENT] = 'COMMENT'


def group(*choices, **kwargs):
    capture = kwargs.pop('capture', False)  # Python 2, arrghhhhh :(
    assert not kwargs

    start = '('
    if not capture:
        start += '?:'
    return start + '|'.join(choices) + ')'

def any(*choices):
    return group(*choices) + '*'

def maybe(*choices):
    return group(*choices) + '?'

# Note: we use unicode matching for names ("\w") but ascii matching for
# number literals.
Whitespace = r'[ \f\t]*'
Comment = r'#[^\r\n]*'
Name = r'\w+'

if py_version >= 36:
    Hexnumber = r'0[xX](?:_?[0-9a-fA-F])+'
    Binnumber = r'0[bB](?:_?[01])+'
    Octnumber = r'0[oO](?:_?[0-7])+'
    Decnumber = r'(?:0(?:_?0)*|[1-9](?:_?[0-9])*)'
    Intnumber = group(Hexnumber, Binnumber, Octnumber, Decnumber)
    Exponent = r'[eE][-+]?[0-9](?:_?[0-9])*'
    Pointfloat = group(r'[0-9](?:_?[0-9])*\.(?:[0-9](?:_?[0-9])*)?',
                       r'\.[0-9](?:_?[0-9])*') + maybe(Exponent)
    Expfloat = r'[0-9](?:_?[0-9])*' + Exponent
    Floatnumber = group(Pointfloat, Expfloat)
    Imagnumber = group(r'[0-9](?:_?[0-9])*[jJ]', Floatnumber + r'[jJ]')
else:
    Hexnumber = r'0[xX][0-9a-fA-F]+'
    Binnumber = r'0[bB][01]+'
    if is_py3:
        Octnumber = r'0[oO][0-7]+'
    else:
        Octnumber = '0[0-7]+'
    Decnumber = r'(?:0+|[1-9][0-9]*)'
    Intnumber = group(Hexnumber, Binnumber, Octnumber, Decnumber)
    Exponent = r'[eE][-+]?[0-9]+'
    Pointfloat = group(r'[0-9]+\.[0-9]*', r'\.[0-9]+') + maybe(Exponent)
    Expfloat = r'[0-9]+' + Exponent
    Floatnumber = group(Pointfloat, Expfloat)
    Imagnumber = group(r'[0-9]+[jJ]', Floatnumber + r'[jJ]')
Number = group(Imagnumber, Floatnumber, Intnumber)

# Return the empty string, plus all of the valid string prefixes.
def _all_string_prefixes():
    # The valid string prefixes. Only contain the lower case versions,
    #  and don't contain any permuations (include 'fr', but not
    #  'rf'). The various permutations will be generated.
    _valid_string_prefixes = ['b', 'r', 'u', 'br']
    if py_version >= 36:
        _valid_string_prefixes += ['f', 'fr']
    if py_version <= 27:
        # TODO this is actually not 100% valid. ur is valid in Python 2.7,
        # while ru is not.
        _valid_string_prefixes.append('ur')

    # if we add binary f-strings, add: ['fb', 'fbr']
    result = set([''])
    for prefix in _valid_string_prefixes:
        for t in _itertools.permutations(prefix):
            # create a list with upper and lower versions of each
            #  character
            for u in _itertools.product(*[(c, c.upper()) for c in t]):
                result.add(''.join(u))
    return result

def _compile(expr):
    return re.compile(expr, re.UNICODE)

# Note that since _all_string_prefixes includes the empty string,
#  StringPrefix can be the empty string (making it optional).
StringPrefix = group(*_all_string_prefixes())

# Tail end of ' string.
Single = r"[^'\\]*(?:\\.[^'\\]*)*'"
# Tail end of " string.
Double = r'[^"\\]*(?:\\.[^"\\]*)*"'
# Tail end of ''' string.
Single3 = r"[^'\\]*(?:(?:\\.|'(?!''))[^'\\]*)*'''"
# Tail end of """ string.
Double3 = r'[^"\\]*(?:(?:\\.|"(?!""))[^"\\]*)*"""'
Triple = group(StringPrefix + "'''", StringPrefix + '"""')

# Because of leftmost-then-longest match semantics, be sure to put the
# longest operators first (e.g., if = came before ==, == would get
# recognized as two instances of =).
Operator = group(r"\*\*=?", r">>=?", r"<<=?", r"!=",
                 r"//=?", r"->",
                 r"[+\-*/%&@|^=<>]=?",
                 r"~")

Bracket = '[][(){}]'
Special = group(r'\r?\n', r'\.\.\.', r'[:;.,@]')
Funny = group(Operator, Bracket, Special)

PlainToken = group(Number, Funny, Name, capture=True)

# First (or only) line of ' or " string.
ContStr = group(StringPrefix + r"'[^\n'\\]*(?:\\.[^\n'\\]*)*" +
                group("'", r'\\\r?\n'),
                StringPrefix + r'"[^\n"\\]*(?:\\.[^\n"\\]*)*' +
                group('"', r'\\\r?\n'))
PseudoExtras = group(r'\\\r?\n|\Z', Comment, Triple)
PseudoToken = group(Whitespace, capture=True) + \
    group(PseudoExtras, Number, Funny, ContStr, Name, capture=True)

# For a given string prefix plus quotes, endpats maps it to a regex
#  to match the remainder of that string. _prefix can be empty, for
#  a normal single or triple quoted string (with no prefix).
endpats = {}
for _prefix in _all_string_prefixes():
    endpats[_prefix + "'"] = _compile(Single)
    endpats[_prefix + '"'] = _compile(Double)
    endpats[_prefix + "'''"] = _compile(Single3)
    endpats[_prefix + '"""'] = _compile(Double3)

# A set of all of the single and triple quoted string prefixes,
#  including the opening quotes.
single_quoted = set()
triple_quoted = set()
for t in _all_string_prefixes():
    for p in (t + '"', t + "'"):
        single_quoted.add(p)
    for p in (t + '"""', t + "'''"):
        triple_quoted.add(p)


# TODO add with?
ALWAYS_BREAK_TOKENS = (';', 'import', 'class', 'def', 'try', 'except',
                       'finally', 'while', 'return')
pseudo_token_compiled = _compile(PseudoToken)


class TokenInfo(namedtuple('Token', ['type', 'string', 'start_pos', 'prefix'])):
    def __repr__(self):
        return ('TokenInfo(type=%s, string=%r, start=%r, prefix=%r)' %
                self._replace(type=self.get_type_name()))

    def get_type_name(self, exact=True):
        if exact:
            typ = self.exact_type
        else:
            typ = self.type
        return tok_name[typ]

    @property
    def exact_type(self):
        if self.type == OP and self.string in opmap:
            return opmap[self.string]
        else:
            return self.type

    @property
    def end_pos(self):
        lines = splitlines(self.string)
        if len(lines) > 1:
            return self.start_pos[0] + len(lines) - 1, 0
        else:
            return self.start_pos[0], self.start_pos[1] + len(self.string)


def source_tokens(source, use_exact_op_types=False):
    """Generate tokens from a the source code (string)."""
    lines = splitlines(source, keepends=True)
    return generate_tokens(lines, use_exact_op_types)


def generate_tokens(lines, use_exact_op_types=False):
    """
    A heavily modified Python standard library tokenizer.

    Additionally to the default information, yields also the prefix of each
    token. This idea comes from lib2to3. The prefix contains all information
    that is irrelevant for the parser like newlines in parentheses or comments.
    """
    paren_level = 0  # count parentheses
    indents = [0]
    max = 0
    numchars = '0123456789'
    contstr = ''
    contline = None
    # We start with a newline. This makes indent at the first position
    # possible. It's not valid Python, but still better than an INDENT in the
    # second line (and not in the first). This makes quite a few things in
    # Jedi's fast parser possible.
    new_line = True
    prefix = ''  # Should never be required, but here for safety
    additional_prefix = ''
    for lnum, line in enumerate(lines, 1):  # loop over lines in stream
        pos, max = 0, len(line)

        if contstr:                                         # continued string
            endmatch = endprog.match(line)
            if endmatch:
                pos = endmatch.end(0)
                yield TokenInfo(STRING, contstr + line[:pos], contstr_start, prefix)
                contstr = ''
                contline = None
            else:
                contstr = contstr + line
                contline = contline + line
                continue

        while pos < max:
            pseudomatch = pseudo_token_compiled.match(line, pos)
            if not pseudomatch:                             # scan for tokens
                txt = line[pos:]
                if txt.endswith('\n'):
                    new_line = True
                yield TokenInfo(ERRORTOKEN, txt, (lnum, pos), prefix)
                break

            prefix = additional_prefix + pseudomatch.group(1)
            additional_prefix = ''
            start, pos = pseudomatch.span(2)
            spos = (lnum, start)
            token = pseudomatch.group(2)
            initial = token[0]

            if new_line and initial not in '\r\n#':
                new_line = False
                if paren_level == 0:
                    i = 0
                    while line[i] == '\f':
                        i += 1
                        start -= 1
                    if start > indents[-1]:
                        yield TokenInfo(INDENT, '', spos, '')
                        indents.append(start)
                    while start < indents[-1]:
                        yield TokenInfo(DEDENT, '', spos, '')
                        indents.pop()

            if (initial in numchars or                      # ordinary number
                    (initial == '.' and token != '.' and token != '...')):
                yield TokenInfo(NUMBER, token, spos, prefix)
            elif initial in '\r\n':
                if not new_line and paren_level == 0:
                    yield TokenInfo(NEWLINE, token, spos, prefix)
                else:
                    additional_prefix = prefix + token
                new_line = True
            elif initial == '#':  # Comments
                assert not token.endswith("\n")
                additional_prefix = prefix + token
            elif token in triple_quoted:
                endprog = endpats[token]
                endmatch = endprog.match(line, pos)
                if endmatch:                                # all on one line
                    pos = endmatch.end(0)
                    token = line[start:pos]
                    yield TokenInfo(STRING, token, spos, prefix)
                else:
                    contstr_start = (lnum, start)           # multiple lines
                    contstr = line[start:]
                    contline = line
                    break
            elif initial in single_quoted or \
                    token[:2] in single_quoted or \
                    token[:3] in single_quoted:
                if token[-1] == '\n':                       # continued string
                    contstr_start = lnum, start
                    endprog = (endpats.get(initial) or endpats.get(token[1])
                               or endpats.get(token[2]))
                    contstr = line[start:]
                    contline = line
                    break
                else:                                       # ordinary string
                    yield TokenInfo(STRING, token, spos, prefix)
            elif is_identifier(initial):                      # ordinary name
                if token in ALWAYS_BREAK_TOKENS:
                    paren_level = 0
                    while True:
                        indent = indents.pop()
                        if indent > start:
                            yield TokenInfo(DEDENT, '', spos, '')
                        else:
                            indents.append(indent)
                            break
                yield TokenInfo(NAME, token, spos, prefix)
            elif initial == '\\' and line[start:] in ('\\\n', '\\\r\n'):  # continued stmt
                additional_prefix += prefix + line[start:]
                break
            else:
                if token in '([{':
                    paren_level += 1
                elif token in ')]}':
                    paren_level -= 1

                try:
                    # This check is needed in any case to check if it's a valid
                    # operator or just some random unicode character.
                    exact_type = opmap[token]
                except KeyError:
                    exact_type = typ = ERRORTOKEN
                if use_exact_op_types:
                    typ = exact_type
                else:
                    typ = OP
                yield TokenInfo(typ, token, spos, prefix)

    if contstr:
        yield TokenInfo(ERRORTOKEN, contstr, contstr_start, prefix)
        if contstr.endswith('\n'):
            new_line = True

    end_pos = lnum, max
    # As the last position we just take the maximally possible position. We
    # remove -1 for the last new line.
    for indent in indents[1:]:
        yield TokenInfo(DEDENT, '', end_pos, '')
    yield TokenInfo(ENDMARKER, '', end_pos, additional_prefix)


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2:
        path = sys.argv[1]
        with open(path) as f:
            code = u(f.read())
    else:
        code = u(sys.stdin.read())
    for token in source_tokens(code, use_exact_op_types=True):
        print(token)
