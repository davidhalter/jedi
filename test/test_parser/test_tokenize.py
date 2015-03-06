from jedi._compatibility import u
from jedi import parser
from token import STRING

from ..helpers import unittest


class TokenTest(unittest.TestCase):
    def test_end_pos_one_line(self):
        parsed = parser.Parser(u('''
def testit():
    a = "huhu"
'''))
        tok = parsed.module.subscopes[0].statements[0]._token_list[2]
        self.assertEqual(tok.end_pos, (3, 14))

    def test_end_pos_multi_line(self):
        parsed = parser.Parser(u('''
def testit():
    a = """huhu
asdfasdf""" + "h"
'''))
        tok = parsed.module.subscopes[0].statements[0]._token_list[2]
        self.assertEqual(tok.end_pos, (4, 11))

    def test_quoted_strings(self):

        string_tokens = [
            'u"test"',
            'u"""test"""',
            'U"""test"""',
            "u'''test'''",
            "U'''test'''",
        ]

        for s in string_tokens:
            parsed = parser.Parser(u('''a = %s\n''' % s))
            tok_list = parsed.module.statements[0]._token_list
            self.assertEqual(len(tok_list), 3)
            tok = tok_list[2]
            self.assertIsInstance(tok, parser.tokenize.Token)
            self.assertEqual(tok.type, STRING)


def test_tokenizer_with_string_literal_backslash():
    import jedi
    c = jedi.Script("statement = u'foo\\\n'; statement").goto_definitions()
    assert c[0]._name.parent.parent.obj == 'foo'
