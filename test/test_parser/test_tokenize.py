from jedi._compatibility import u
from jedi import parser

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
