from io import StringIO
from token import NEWLINE, STRING

from jedi._compatibility import u
from jedi import parser

from ..helpers import unittest


class TokenTest(unittest.TestCase):
    def test_end_pos_one_line(self):
        parsed = parser.Parser(parser.load_grammar(), u('''
def testit():
    a = "huhu"
'''))
        tok = parsed.module.subscopes[0].statements[0].children[2]
        self.assertEqual(tok.end_pos, (3, 14))

    def test_end_pos_multi_line(self):
        parsed = parser.Parser(parser.load_grammar(), u('''
def testit():
    a = """huhu
asdfasdf""" + "h"
'''))
        tok = parsed.module.subscopes[0].statements[0].children[2].children[0]
        self.assertEqual(tok.end_pos, (4, 11))

    def test_simple_no_whitespace(self):
        # Test a simple one line string, no preceding whitespace
        simple_docstring = '"""simple one line docstring"""'
        simple_docstring_io = StringIO(simple_docstring)
        tokens = parser.tokenize.generate_tokens(simple_docstring_io.readline)
        token_list = list(tokens)
        string_token = token_list[0]
        self.assertEqual(string_token._preceding_whitespace, '')
        self.assertEqual(string_token.string, '"""simple one line docstring"""')

    def test_simple_with_whitespace(self):
        # Test a simple one line string with preceding whitespace and newline
        simple_docstring = '  """simple one line docstring""" \r\n'
        simple_docstring_io = StringIO(simple_docstring)
        tokens = parser.tokenize.generate_tokens(simple_docstring_io.readline)
        token_list = list(tokens)
        string_token = token_list[0]
        self.assertEqual(string_token._preceding_whitespace, '  ')
        self.assertEqual(string_token.string, '"""simple one line docstring"""')
        self.assertEqual(string_token.type, STRING)
        newline_token = token_list[1]
        self.assertEqual(newline_token._preceding_whitespace, ' ')
        self.assertEqual(newline_token.type, NEWLINE)

    def test_function_whitespace(self):
        # Test function definition whitespace identification
        fundef = '''def test_whitespace(*args, **kwargs):
    x = 1
    if x > 0:
        print(True)
'''
        fundef_io = StringIO(fundef)
        tokens = parser.tokenize.generate_tokens(fundef_io.readline)
        token_list = list(tokens)
        print(token_list)
        for t in token_list:
            if t.string == 'test_whitespace':
                self.assertEqual(t._preceding_whitespace, ' ')
            if t.string == '(':
                self.assertEqual(t._preceding_whitespace, '')
            if t.string == '*':
                self.assertEqual(t._preceding_whitespace, '')
            if t.string == '**':
                self.assertEqual(t._preceding_whitespace, ' ')
            if t.string == 'print':
                self.assertEqual(t._preceding_whitespace, '        ')
            if t.string == 'if':
                self.assertEqual(t._preceding_whitespace, '    ')


def test_tokenizer_with_string_literal_backslash():
    import jedi
    c = jedi.Script("statement = u'foo\\\n'; statement").goto_definitions()
    assert c[0]._name.parent.obj == 'foo'
