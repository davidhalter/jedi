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
        _, value, _, prefix = token_list[0]
        self.assertEqual(prefix, '')
        self.assertEqual(value, '"""simple one line docstring"""')

    def test_simple_with_whitespace(self):
        # Test a simple one line string with preceding whitespace and newline
        simple_docstring = '  """simple one line docstring""" \r\n'
        simple_docstring_io = StringIO(simple_docstring)
        tokens = parser.tokenize.generate_tokens(simple_docstring_io.readline)
        token_list = list(tokens)
        typ, value, start_pos, prefix = token_list[0]
        self.assertEqual(prefix, '  ')
        self.assertEqual(value, '"""simple one line docstring"""')
        self.assertEqual(typ, STRING)
        typ, value, start_pos, prefix = token_list[1]
        self.assertEqual(prefix, ' ')
        self.assertEqual(typ, NEWLINE)

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
        for _, value, _, prefix in token_list:
            if value == 'test_whitespace':
                self.assertEqual(prefix, ' ')
            if value == '(':
                self.assertEqual(prefix, '')
            if value == '*':
                self.assertEqual(prefix, '')
            if value == '**':
                self.assertEqual(prefix, ' ')
            if value == 'print':
                self.assertEqual(prefix, '        ')
            if value == 'if':
                self.assertEqual(prefix, '    ')


def test_tokenizer_with_string_literal_backslash():
    import jedi
    c = jedi.Script("statement = u'foo\\\n'; statement").goto_definitions()
    assert c[0]._name.parent.obj == 'foo'
