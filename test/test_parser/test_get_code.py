import difflib

import pytest

from jedi._compatibility import u
from jedi.parser import Parser, load_grammar

code_basic_features = u('''
"""A mod docstring"""

def a_function(a_argument, a_default = "default"):
    """A func docstring"""

    a_result = 3 * a_argument
    print(a_result)  # a comment
    b = """
from
to""" + "huhu"


    if a_default == "default":
        return str(a_result)
    else
        return None
''')


def diff_code_assert(a, b, n=4):
    if a != b:
        diff = "\n".join(difflib.unified_diff(
            a.splitlines(),
            b.splitlines(),
            n=n,
            lineterm=""
        ))
        assert False, "Code does not match:\n%s\n\ncreated code:\n%s" % (
            diff,
            b
        )
    pass


@pytest.mark.skipif('True', reason='Refactor a few parser things first.')
def test_basic_parsing():
    """Validate the parsing features"""

    prs = Parser(load_grammar(), code_basic_features)
    diff_code_assert(
        code_basic_features,
        prs.module.get_code()
    )


def test_operators():
    src = u('5  * 3')
    prs = Parser(load_grammar(), src)
    diff_code_assert(src, prs.module.get_code())


def test_get_code():
    """Use the same code that the parser also generates, to compare"""
    s = u('''"""a docstring"""
class SomeClass(object, mixin):
    def __init__(self):
        self.xy = 3.0
        """statement docstr"""
    def some_method(self):
        return 1
    def yield_method(self):
        while hasattr(self, 'xy'):
            yield True
        for x in [1, 2]:
            yield x
    def empty(self):
        pass
class Empty:
    pass
class WithDocstring:
    """class docstr"""
    pass
def method_with_docstring():
    """class docstr"""
    pass
''')
    assert Parser(load_grammar(), s).module.get_code() == s


def test_end_newlines():
    """
    The Python grammar explicitly needs a newline at the end. Jedi though still
    wants to be able, to return the exact same code without the additional new
    line the parser needs.
    """
    def test(source, end_pos):
        module = Parser(load_grammar(), u(source)).module
        assert module.get_code() == source
        assert module.end_pos == end_pos

    test('a', (1, 1))
    test('a\n', (2, 0))
    test('a\nb', (2, 1))
    test('a\n#comment\n', (3, 0))
    test('a\n#comment', (2, 8))
    test('a#comment', (1, 9))
    test('def a():\n pass', (2, 5))
