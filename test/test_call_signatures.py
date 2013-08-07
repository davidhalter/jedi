import textwrap

from .base import unittest
from jedi import Script

class TestCallSignatures(unittest.TestCase):
    def assert_call_def(self, call_defs, name, index):
        assert len(call_defs) <= 1
        call_def = call_defs[0] if len(call_defs) else None
        self.assertEqual(
            {'call_name': getattr(call_def, 'call_name', None),
             'index': getattr(call_def, 'index', None)},
            {'call_name': name, 'index': index},
        )

    def test_function_definition(self):
        check = self.assert_call_def

        # simple
        s = "abs(a, str("
        s2 = "abs(), "
        s3 = "abs()."
        # more complicated
        s4 = 'abs(zip(), , set,'
        s5 = "abs(1,\nif 2:\n def a():"
        s6 = "str().center("
        s7 = "str().upper().center("
        s8 = "str(int[zip("

        check(self.function_definition(s, (1, 4)), 'abs', 0)
        check(self.function_definition(s, (1, 6)), 'abs', 1)
        check(self.function_definition(s, (1, 7)), 'abs', 1)
        check(self.function_definition(s, (1, 8)), 'abs', 1)
        check(self.function_definition(s, (1, 11)), 'str', 0)

        check(self.function_definition(s2, (1, 4)), 'abs', 0)
        assert self.function_definition(s2, (1, 5)) is None
        assert self.function_definition(s2) is None

        assert self.function_definition(s3, (1, 5)) is None
        assert self.function_definition(s3) is None

        assert self.function_definition(s4, (1, 3)) is None
        check(self.function_definition(s4, (1, 4)), 'abs', 0)
        check(self.function_definition(s4, (1, 8)), 'zip', 0)
        check(self.function_definition(s4, (1, 9)), 'abs', 0)
        #check(self.function_definition(s4, (1, 10)), 'abs', 1)

        check(self.function_definition(s5, (1, 4)), 'abs', 0)
        check(self.function_definition(s5, (1, 6)), 'abs', 1)

        check(self.function_definition(s6), 'center', 0)
        check(self.function_definition(s6, (1, 4)), 'str', 0)

        check(self.function_definition(s7), 'center', 0)
        check(self.function_definition(s8), 'zip', 0)
        check(self.function_definition(s8, (1, 8)), 'str', 0)

        s = "import time; abc = time; abc.sleep("
        check(self.function_definition(s), 'sleep', 0)

        # jedi-vim #9
        s = "with open("
        check(self.function_definition(s), 'open', 0)

        # jedi-vim #11
        s1 = "for sorted("
        check(self.function_definition(s1), 'sorted', 0)
        s2 = "for s in sorted("
        check(self.function_definition(s2), 'sorted', 0)

        # jedi #57
        s = "def func(alpha, beta): pass\n" \
            "func(alpha='101',"
        check(self.function_definition(s, (2, 13)), 'func', 0)

    def test_function_definition_complex(self):
        check = self.assert_call_def

        s = """
                def abc(a,b):
                    pass

                def a(self):
                    abc(

                if 1:
                    pass
            """
        check(self.function_definition(s, (6, 24)), 'abc', 0)
        s = """
                import re
                def huhu(it):
                    re.compile(
                    return it * 2
            """
        check(self.function_definition(s, (4, 31)), 'compile', 0)
        # jedi-vim #70
        s = """def foo("""
        assert self.function_definition(s) is None
        # jedi-vim #116
        s = """import functools; test = getattr(functools, 'partial'); test("""
        check(self.function_definition(s), 'partial', 0)

    def test_call_signature_on_module(self):
        """github issue #240"""
        s = 'import datetime; datetime('
        # just don't throw an exception (if numpy doesn't exist, just ignore it)
        assert Script(s).call_signatures() == []

    def test_function_definition_empty_paren_pre_space(self):
        s = textwrap.dedent("""\
        def f(a, b):
            pass
        f( )""")
        call_defs = Script(s, 3, 3).call_signatures()
        self.assert_call_def(call_defs, 'f', 0)
