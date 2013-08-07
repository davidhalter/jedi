import textwrap

from .base import unittest
from jedi import Script

class TestCallSignatures(unittest.TestCase):
    def _assert_call_def(self, call_defs, name, index):
        # just for the sake of this simple comparison
        assert len(call_defs) <= 1

        if not call_defs:
            assert name is None
        else:
            assert call_defs[0].call_name == name
            assert call_defs[0].index == index

    def test_call_signatures(self):
        def _run(source, expected_name, expected_index=0, column=None, line=None):
            signatures = Script(source, line, column).call_signatures()
            self._assert_call_def(signatures, expected_name, expected_index)

        def run(source, name, index=0, column=None, line=1):
            _run(source, name, index, column, line)

        # simple
        s1 = "abs(a, str("
        run(s1, 'abs', 0, 4)
        run(s1, 'abs', 1, 6)
        run(s1, 'abs', 1, 7)
        run(s1, 'abs', 1, 8)
        run(s1, 'str', 0, 11)

        s2 = "abs(), "
        run(s2, 'abs', 0, 4)
        run(s2, None, column=5)
        run(s2, None)

        s3 = "abs()."
        run(s3, None, column=5)
        run(s3, None)

        # more complicated
        s4 = 'abs(zip(), , set,'
        run(s4, None, column=3)
        run(s4, 'abs', 0, 4)
        run(s4, 'zip', 0, 8)
        run(s4, 'abs', 0, 9)
        #run(s4, 'abs', 1, 10)


        s5 = "abs(1,\nif 2:\n def a():"
        print Script(s5, 1, 4).call_signatures()
        #check(self.function_definition(s5, (1, 6)), 'abs', 1)
        run(s5, 'abs', 0, 4)
        run(s5, 'abs', 1, 6)

        s6 = "str().center("
        run(s6, 'center', 0)
        run(s6, 'str', 0, 4)

        s7 = "str().upper().center("
        s8 = "str(int[zip("
        run(s7, 'center', 0)
        run(s8, 'zip', 0)
        run(s8, 'str', 0, 8)

        run("import time; abc = time; abc.sleep(", 'sleep', 0)

        # jedi-vim #9
        run("with open(", 'open', 0)

        # jedi-vim #11
        run("for sorted(", 'sorted', 0)
        run("for s in sorted(", 'sorted', 0)

        # jedi #57
        s = "def func(alpha, beta): pass\n" \
            "func(alpha='101',"
        run(s, 'func', 0, column=13, line=2)

    def test_function_definition_complex(self):
        check = self._assert_call_def

        s = """
                def abc(a,b):
                    pass

                def a(self):
                    abc(

                if 1:
                    pass
            """
        check(Script(s, 6, 24).call_signatures(), 'abc', 0)
        s = """
                import re
                def huhu(it):
                    re.compile(
                    return it * 2
            """
        check(Script(s, 4, 31).call_signatures(), 'compile', 0)
        # jedi-vim #70
        s = """def foo("""
        assert Script(s).call_signatures() == []
        # jedi-vim #116
        s = """import functools; test = getattr(functools, 'partial'); test("""
        check(Script(s).call_signatures(), 'partial', 0)

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
        self._assert_call_def(call_defs, 'f', 0)
