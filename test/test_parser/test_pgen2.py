"""Test suite for 2to3's parser and grammar files.

This is the place to add tests for changes to 2to3's grammar, such as those
merging the grammars for Python 2 and 3. In addition to specific tests for
parts of the grammar we've changed, we also make sure we can parse the
test_grammar.py files from both Python 2 and Python 3.
"""

from textwrap import dedent


from jedi._compatibility import unicode, is_py3
from jedi.parser import Parser, load_grammar, ParseError
import pytest

from test.helpers import TestCase


def parse(code, version='3.4'):
    code = dedent(code) + "\n\n"
    grammar = load_grammar(version=version)
    return Parser(grammar, unicode(code), 'file_input').get_parsed_node()


class TestDriver(TestCase):

    def test_formfeed(self):
        s = """print 1\n\x0Cprint 2\n"""
        t = parse(s, '2.7')
        self.assertEqual(t.children[0].children[0].type, 'print_stmt')
        self.assertEqual(t.children[1].children[0].type, 'print_stmt')
        s = """1\n\x0C\x0C2\n"""
        t = parse(s, '2.7')


class GrammarTest(TestCase):
    def invalid_syntax(self, code, **kwargs):
        try:
            parse(code, **kwargs)
        except ParseError:
            pass
        else:
            raise AssertionError("Syntax shouldn't have been valid")


class TestMatrixMultiplication(GrammarTest):
    @pytest.mark.skipif('sys.version_info[:2] < (3, 5)')
    def test_matrix_multiplication_operator(self):
        parse("a @ b", "3.5")
        parse("a @= b", "3.5")


class TestYieldFrom(GrammarTest):
    def test_yield_from(self):
        parse("yield from x")
        parse("(yield from x) + y")
        self.invalid_syntax("yield from")


class TestAsyncAwait(GrammarTest):
    @pytest.mark.skipif('sys.version_info[:2] < (3, 5)')
    def test_await_expr(self):
        parse("""async def foo():
                             await x
                      """, "3.5")

        parse("""async def foo():

            def foo(): pass

            def foo(): pass

            await x
        """, "3.5")

        parse("""async def foo(): return await a""", "3.5")

        parse("""def foo():
            def foo(): pass
            async def foo(): await x
        """, "3.5")

    @pytest.mark.skipif('sys.version_info[:2] < (3, 5)')
    @pytest.mark.xfail(reason="acting like python 3.7")
    def test_await_expr_invalid(self):
        self.invalid_syntax("await x", version="3.5")
        self.invalid_syntax("""def foo():
                                   await x""", version="3.5")

        self.invalid_syntax("""def foo():
            def foo(): pass
            async def foo(): pass
            await x
        """, version="3.5")

    @pytest.mark.skipif('sys.version_info[:2] < (3, 5)')
    @pytest.mark.xfail(reason="acting like python 3.7")
    def test_async_var(self):
        parse("""async = 1""", "3.5")
        parse("""await = 1""", "3.5")
        parse("""def async(): pass""", "3.5")

    @pytest.mark.skipif('sys.version_info[:2] < (3, 5)')
    def test_async_for(self):
        parse("""async def foo():
                             async for a in b: pass""", "3.5")

    @pytest.mark.skipif('sys.version_info[:2] < (3, 5)')
    @pytest.mark.xfail(reason="acting like python 3.7")
    def test_async_for_invalid(self):
        self.invalid_syntax("""def foo():
                                   async for a in b: pass""", version="3.5")

    @pytest.mark.skipif('sys.version_info[:2] < (3, 5)')
    def test_async_with(self):
        parse("""async def foo():
                             async with a: pass""", "3.5")

    @pytest.mark.skipif('sys.version_info[:2] < (3, 5)')
    @pytest.mark.xfail(reason="acting like python 3.7")
    def test_async_with_invalid(self):
        self.invalid_syntax("""def foo():
                                   async with a: pass""", version="3.5")


class TestRaiseChanges(GrammarTest):
    def test_2x_style_1(self):
        parse("raise")

    def test_2x_style_2(self):
        parse("raise E, V", version='2.7')

    def test_2x_style_3(self):
        parse("raise E, V, T", version='2.7')

    def test_2x_style_invalid_1(self):
        self.invalid_syntax("raise E, V, T, Z", version='2.7')

    def test_3x_style(self):
        parse("raise E1 from E2")

    def test_3x_style_invalid_1(self):
        self.invalid_syntax("raise E, V from E1")

    def test_3x_style_invalid_2(self):
        self.invalid_syntax("raise E from E1, E2")

    def test_3x_style_invalid_3(self):
        self.invalid_syntax("raise from E1, E2")

    def test_3x_style_invalid_4(self):
        self.invalid_syntax("raise E from")


# Adapted from Python 3's Lib/test/test_grammar.py:GrammarTests.testFuncdef
class TestFunctionAnnotations(GrammarTest):
    def test_1(self):
        parse("""def f(x) -> list: pass""")

    def test_2(self):
        parse("""def f(x:int): pass""")

    def test_3(self):
        parse("""def f(*x:str): pass""")

    def test_4(self):
        parse("""def f(**x:float): pass""")

    def test_5(self):
        parse("""def f(x, y:1+2): pass""")

    def test_6(self):
        self.invalid_syntax("""def f(a, (b:1, c:2, d)): pass""")

    def test_7(self):
        self.invalid_syntax("""def f(a, (b:1, c:2, d), e:3=4, f=5, *g:6): pass""")

    def test_8(self):
        s = """def f(a, (b:1, c:2, d), e:3=4, f=5,
                        *g:6, h:7, i=8, j:9=10, **k:11) -> 12: pass"""
        self.invalid_syntax(s)


class TestExcept(GrammarTest):
    def test_new(self):
        s = """
            try:
                x
            except E as N:
                y"""
        parse(s)

    def test_old(self):
        s = """
            try:
                x
            except E, N:
                y"""
        parse(s, version='2.7')


# Adapted from Python 3's Lib/test/test_grammar.py:GrammarTests.testAtoms
class TestSetLiteral(GrammarTest):
    def test_1(self):
        parse("""x = {'one'}""")

    def test_2(self):
        parse("""x = {'one', 1,}""")

    def test_3(self):
        parse("""x = {'one', 'two', 'three'}""")

    def test_4(self):
        parse("""x = {2, 3, 4,}""")


class TestNumericLiterals(GrammarTest):
    def test_new_octal_notation(self):
        code = """0o7777777777777"""
        if is_py3:
            parse(code)
        else:
            self.invalid_syntax(code)
        self.invalid_syntax("""0o7324528887""")

    def test_new_binary_notation(self):
        parse("""0b101010""")
        self.invalid_syntax("""0b0101021""")


class TestClassDef(GrammarTest):
    def test_new_syntax(self):
        parse("class B(t=7): pass")
        parse("class B(t, *args): pass")
        parse("class B(t, **kwargs): pass")
        parse("class B(t, *args, **kwargs): pass")
        parse("class B(t, y=9, *args, **kwargs): pass")


class TestParserIdempotency(TestCase):
    """A cut-down version of pytree_idempotency.py."""
    def test_extended_unpacking(self):
        parse("a, *b, c = x\n")
        parse("[*a, b] = x\n")
        parse("(z, *y, w) = m\n")
        parse("for *z, m in d: pass\n")


class TestLiterals(GrammarTest):
    # It's not possible to get the same result when using \xaa in Python 2/3,
    # because it's treated differently.
    @pytest.mark.skipif('sys.version_info[0] < 3')
    def test_multiline_bytes_literals(self):
        s = """
            md5test(b"\xaa" * 80,
                    (b"Test Using Larger Than Block-Size Key "
                     b"and Larger Than One Block-Size Data"),
                    "6f630fad67cda0ee1fb1f562db3aa53e")
            """
        parse(s)

    def test_multiline_bytes_tripquote_literals(self):
        s = '''
            b"""
            <?xml version="1.0" encoding="UTF-8"?>
            <!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN">
            """
            '''
        parse(s)

    @pytest.mark.skipif('sys.version_info[0] < 3')
    def test_multiline_str_literals(self):
        s = """
            md5test("\xaa" * 80,
                    ("Test Using Larger Than Block-Size Key "
                     "and Larger Than One Block-Size Data"),
                    "6f630fad67cda0ee1fb1f562db3aa53e")
            """
        parse(s)
