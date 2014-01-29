import jedi.parser as parser

try:
    import unittest2 as unittest
except ImportError:  # pragma: no cover
    import unittest


class TokenTest(unittest.TestCase):
    def test_end_pos_one_line(self):
        parsed = parser.Parser('''
def testit():
    a = "huhu"
''')
        tok = parsed.top_module.subscopes[0].statements[0].token_list[2]
        self.assertEqual(tok.end_pos, (3, 14))

    def test_end_pos_multi_line(self):
        parsed = parser.Parser('''
def testit():
    a = """huhu
asdfasdf""" + "h"
''')
        tok = parsed.top_module.subscopes[0].statements[0].token_list[2]
        self.assertEqual(tok.end_pos, (4, 11))
