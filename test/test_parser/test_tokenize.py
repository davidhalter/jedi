# -*- coding: utf-8    # This file contains Unicode characters.

from io import StringIO
from textwrap import dedent

import pytest

from jedi._compatibility import u, is_py3
from jedi.parser.token import NAME, OP, NEWLINE, STRING, INDENT
from jedi.parser import Parser, load_grammar, tokenize


from ..helpers import unittest


class TokenTest(unittest.TestCase):
    def test_end_pos_one_line(self):
        parsed = Parser(load_grammar(), dedent(u('''
        def testit():
            a = "huhu"
        ''')))
        tok = parsed.module.subscopes[0].statements[0].children[2]
        assert tok.end_pos == (3, 14)

    def test_end_pos_multi_line(self):
        parsed = Parser(load_grammar(), dedent(u('''
        def testit():
            a = """huhu
        asdfasdf""" + "h"
        ''')))
        tok = parsed.module.subscopes[0].statements[0].children[2].children[0]
        assert tok.end_pos == (4, 11)

    def test_simple_no_whitespace(self):
        # Test a simple one line string, no preceding whitespace
        simple_docstring = u('"""simple one line docstring"""')
        simple_docstring_io = StringIO(simple_docstring)
        tokens = tokenize.generate_tokens(simple_docstring_io.readline)
        token_list = list(tokens)
        _, value, _, prefix = token_list[0]
        assert prefix == ''
        assert value == '"""simple one line docstring"""'

    def test_simple_with_whitespace(self):
        # Test a simple one line string with preceding whitespace and newline
        simple_docstring = u('  """simple one line docstring""" \r\n')
        simple_docstring_io = StringIO(simple_docstring)
        tokens = tokenize.generate_tokens(simple_docstring_io.readline)
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
        fundef = dedent(u('''
        def test_whitespace(*args, **kwargs):
            x = 1
            if x > 0:
                print(True)
        '''))
        fundef_io = StringIO(fundef)
        tokens = tokenize.generate_tokens(fundef_io.readline)
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

    def test_identifier_contains_unicode(self):
        fundef = dedent(u('''
        def 我あφ():
            pass
        '''))
        fundef_io = StringIO(fundef)
        tokens = tokenize.generate_tokens(fundef_io.readline)
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
            parsed = Parser(load_grammar(), u('''a = %s\n''' % s))
            simple_stmt = parsed.module.children[0]
            expr_stmt = simple_stmt.children[0]
            assert len(expr_stmt.children) == 3
            string_tok = expr_stmt.children[2]
            assert string_tok.type == 'string'
            assert string_tok.value == s
            assert string_tok.eval() == 'test'


def test_tokenizer_with_string_literal_backslash():
    import jedi
    c = jedi.Script("statement = u'foo\\\n'; statement").goto_definitions()
    assert c[0]._name.parent.obj == 'foo'


def test_ur_literals():
    """
    Decided to parse `u''` literals regardless of Python version. This makes
    probably sense:

    - Python 3.2 doesn't support it and is still supported by Jedi, but might
      not be. While this is incorrect, it's just incorrect for one "old" and in
      the future not very important version.
    - All the other Python versions work very well with it.
    """
    def check(literal):
        io = StringIO(u(literal))
        tokens = tokenize.generate_tokens(io.readline)
        token_list = list(tokens)
        typ, result_literal, _, _ = token_list[0]
        assert typ == STRING
        assert result_literal == literal

    check('u""')
    check('ur""')
    check('Ur""')
    check('UR""')
    check('bR""')
    # Must be in the right order.
    with pytest.raises(AssertionError):
        check('Rb""')
