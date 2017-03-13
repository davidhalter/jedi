# -*- coding: utf-8    # This file contains Unicode characters.

from textwrap import dedent

from jedi._compatibility import is_py3, py_version
from jedi.parser.token import NAME, OP, NEWLINE, STRING, INDENT, ERRORTOKEN, ENDMARKER
from jedi.parser import tokenize
from jedi.parser.python import parse
from jedi.common import splitlines
from jedi.parser.tokenize import TokenInfo


from ..helpers import unittest

def _get_token_list(string):
    return list(tokenize.source_tokens(string))


class TokenTest(unittest.TestCase):
    def test_end_pos_one_line(self):
        parsed = parse(dedent('''
        def testit():
            a = "huhu"
        '''))
        tok = parsed.subscopes[0].statements[0].children[2]
        assert tok.end_pos == (3, 14)

    def test_end_pos_multi_line(self):
        parsed = parse(dedent('''
        def testit():
            a = """huhu
        asdfasdf""" + "h"
        '''))
        tok = parsed.subscopes[0].statements[0].children[2].children[0]
        assert tok.end_pos == (4, 11)

    def test_simple_no_whitespace(self):
        # Test a simple one line string, no preceding whitespace
        simple_docstring = '"""simple one line docstring"""'
        tokens = tokenize.source_tokens(simple_docstring)
        token_list = list(tokens)
        _, value, _, prefix = token_list[0]
        assert prefix == ''
        assert value == '"""simple one line docstring"""'

    def test_simple_with_whitespace(self):
        # Test a simple one line string with preceding whitespace and newline
        simple_docstring = '  """simple one line docstring""" \r\n'
        tokens = tokenize.source_tokens(simple_docstring)
        token_list = list(tokens)
        assert token_list[0][0] == INDENT
        typ, value, start_pos, prefix = token_list[1]
        assert prefix == '  '
        assert value == '"""simple one line docstring"""'
        assert typ == STRING
        typ, value, start_pos, prefix = token_list[2]
        assert prefix == ' '
        assert typ == NEWLINE

    def test_function_whitespace(self):
        # Test function definition whitespace identification
        fundef = dedent('''
        def test_whitespace(*args, **kwargs):
            x = 1
            if x > 0:
                print(True)
        ''')
        tokens = tokenize.source_tokens(fundef)
        token_list = list(tokens)
        for _, value, _, prefix in token_list:
            if value == 'test_whitespace':
                assert prefix == ' '
            if value == '(':
                assert prefix == ''
            if value == '*':
                assert prefix == ''
            if value == '**':
                assert prefix == ' '
            if value == 'print':
                assert prefix == '        '
            if value == 'if':
                assert prefix == '    '

    def test_tokenize_multiline_I(self):
        # Make sure multiline string having newlines have the end marker on the
        # next line
        fundef = '''""""\n'''
        tokens = tokenize.source_tokens(fundef)
        token_list = list(tokens)
        assert token_list == [TokenInfo(ERRORTOKEN, '""""\n', (1, 0), ''),
                              TokenInfo(ENDMARKER ,       '', (2, 0), '')]

    def test_tokenize_multiline_II(self):
        # Make sure multiline string having no newlines have the end marker on
        # same line
        fundef = '''""""'''
        tokens = tokenize.source_tokens(fundef)
        token_list = list(tokens)
        assert token_list == [TokenInfo(ERRORTOKEN, '""""', (1, 0), ''),
                              TokenInfo(ENDMARKER,      '', (1, 4), '')]

    def test_tokenize_multiline_III(self):
        # Make sure multiline string having newlines have the end marker on the
        # next line even if several newline
        fundef = '''""""\n\n'''
        tokens = tokenize.source_tokens(fundef)
        token_list = list(tokens)
        assert token_list == [TokenInfo(ERRORTOKEN, '""""\n\n', (1, 0), ''),
                              TokenInfo(ENDMARKER,          '', (3, 0), '')]

    def test_identifier_contains_unicode(self):
        fundef = dedent('''
        def 我あφ():
            pass
        ''')
        tokens = tokenize.source_tokens(fundef)
        token_list = list(tokens)
        unicode_token = token_list[1]
        if is_py3:
            assert unicode_token[0] == NAME
        else:
            # Unicode tokens in Python 2 seem to be identified as operators.
            # They will be ignored in the parser, that's ok.
            assert unicode_token[0] == OP

    def test_quoted_strings(self):

        string_tokens = [
            'u"test"',
            'u"""test"""',
            'U"""test"""',
            "u'''test'''",
            "U'''test'''",
        ]

        for s in string_tokens:
            module = parse('''a = %s\n''' % s)
            simple_stmt = module.children[0]
            expr_stmt = simple_stmt.children[0]
            assert len(expr_stmt.children) == 3
            string_tok = expr_stmt.children[2]
            assert string_tok.type == 'string'
            assert string_tok.value == s
            assert string_tok.eval() == 'test'


def test_tokenizer_with_string_literal_backslash():
    import jedi
    c = jedi.Script("statement = u'foo\\\n'; statement").goto_definitions()
    assert c[0]._name._context.obj == 'foo'


def test_ur_literals():
    """
    Decided to parse `u''` literals regardless of Python version. This makes
    probably sense:

    - Python 3+ doesn't support it, but it doesn't hurt
      not be. While this is incorrect, it's just incorrect for one "old" and in
      the future not very important version.
    - All the other Python versions work very well with it.
    """
    def check(literal, is_literal=True):
        token_list = _get_token_list(literal)
        typ, result_literal, _, _ = token_list[0]
        if is_literal:
            assert typ == STRING
            assert result_literal == literal
        else:
            assert typ == NAME

    check('u""')
    check('ur""', is_literal=not is_py3)
    check('Ur""', is_literal=not is_py3)
    check('UR""', is_literal=not is_py3)
    check('bR""')
    # Starting with Python 3.3 this ordering is also possible, but we just
    # enable it for all versions. It doesn't hurt.
    check('Rb""')
    # Starting with Python 3.6 format strings where introduced.
    check('fr""', is_literal=py_version >= 36)
    check('rF""', is_literal=py_version >= 36)
    check('f""', is_literal=py_version >= 36)
    check('F""', is_literal=py_version >= 36)


def test_error_literal():
    error_token, endmarker = _get_token_list('"\n')
    assert error_token.type == tokenize.ERRORTOKEN
    assert endmarker.prefix == ''
    assert error_token.string == '"\n'
    assert endmarker.type == tokenize.ENDMARKER
    assert endmarker.prefix == ''

    bracket, error_token, endmarker = _get_token_list('( """')
    assert error_token.type == tokenize.ERRORTOKEN
    assert error_token.prefix == ' '
    assert error_token.string == '"""'
    assert endmarker.type == tokenize.ENDMARKER
    assert endmarker.prefix == ''


def test_endmarker_end_pos():
    def check(code):
        tokens = _get_token_list(code)
        lines = splitlines(code)
        assert tokens[-1].end_pos == (len(lines), len(lines[-1]))

    check('#c')
    check('#c\n')
    check('a\n')
    check('a')
    check(r'a\\n')
    check('a\\')
