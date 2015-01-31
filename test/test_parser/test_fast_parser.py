from textwrap import dedent

import jedi
from jedi._compatibility import u
from jedi import cache
from jedi.parser import load_grammar
from jedi.parser.fast import FastParser


def test_add_to_end():
    """
    fast_parser doesn't parse everything again. It just updates with the
    help of caches, this is an example that didn't work.
    """

    a = """
class Abc():
    def abc(self):
        self.x = 3

class Two(Abc):
    def h(self):
        self
"""  #      ^ here is the first completion

    b = "    def g(self):\n" \
        "        self."
    assert jedi.Script(a, 8, 12, 'example.py').completions()
    assert jedi.Script(a + b, path='example.py').completions()

    a = a[:-1] + '.\n'
    assert jedi.Script(a, 8, 13, 'example.py').completions()
    assert jedi.Script(a + b, path='example.py').completions()


def test_class_in_docstr():
    """
    Regression test for a problem with classes in docstrings.
    """
    a = '"\nclasses\n"'
    jedi.Script(a, 1, 0)._parser

    b = a + '\nimport os'
    assert jedi.Script(b, 4, 8).goto_assignments()


def test_carriage_return_splitting():
    source = u(dedent('''



        "string"

        class Foo():
            pass
        '''))
    source = source.replace('\n', '\r\n')
    p = FastParser(load_grammar(), source)
    assert [n.value for lst in p.module.names_dict.values() for n in lst] == ['Foo']


def check_fp(src, number_parsers_used, number_of_splits=None):
    if number_of_splits is None:
        number_of_splits = number_parsers_used

    p = FastParser(load_grammar(), u(src))
    cache.save_parser(None, None, p, pickling=False)

    # TODO Don't change get_code, the whole thing should be the same.
    # -> Need to refactor the parser first, though.
    assert src == p.module.get_code()
    assert p.number_of_splits == number_of_splits
    assert p.number_parsers_used == number_parsers_used
    return p.module


def test_change_and_undo():
    # Empty the parser cache for the path None.
    cache.parser_cache.pop(None, None)
    func_before = 'def func():\n    pass\n'
    # Parse the function and a.
    check_fp(func_before + 'a', 2)
    # Parse just b.
    check_fp(func_before + 'b', 1, 2)
    # b has changed to a again, so parse that.
    check_fp(func_before + 'a', 1, 2)
    # Same as before no parsers should be used.
    check_fp(func_before + 'a', 0, 2)

    # Getting rid of an old parser: Still no parsers used.
    check_fp('a', 0, 1)
    # Now the file has completely change and we need to parse.
    check_fp('b', 1, 1)
    # And again.
    check_fp('a', 1, 1)


def test_positions():
    # Empty the parser cache for the path None.
    cache.parser_cache.pop(None, None)

    func_before = 'class A:\n pass\n'
    m = check_fp(func_before + 'a', 2)
    assert m.start_pos == (1, 0)
    assert m.end_pos == (3, 1)

    m = check_fp('a', 0, 1)
    assert m.start_pos == (1, 0)
    assert m.end_pos == (1, 1)


def test_if():
    src = dedent('''\
    def func():
        x = 3
        if x:
            def y():
                return x
        return y()

    func()
    ''')

    # Two parsers needed, one for pass and one for the function.
    check_fp(src, 2)
    assert [d.name for d in jedi.Script(src, 8, 6).goto_definitions()] == ['int']


def test_if_simple():
    src = dedent('''\
    if 1:
        a = 3
    ''')
    check_fp(src + 'a', 1)
    check_fp(src + "else:\n    a = ''\na", 1)


def test_for():
    src = dedent("""\
    for a in [1,2]:
        a

    for a1 in 1,"":
        a1
    """)
    check_fp(src, 1)


def test_func_with_if():
    src = dedent("""\
    def recursion(a):
        if foo:
            return recursion(a)
        else:
            if bar:
                return inexistent
            else:
                return a
    """)
    check_fp(src, 1)


def test_decorator():
    src = dedent("""\
    class Decorator():
        @memoize
        def dec(self, a):
            return a
    """)
    check_fp(src, 2)


def test_nested_funcs():
    src = dedent("""\
    def memoize(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    """)
    check_fp(src, 3)


def test_class_and_if():
    src = dedent("""\
    class V:
        def __init__(self):
            pass

        if 1:
            c = 3

    def a_func():
        return 1

    # COMMENT
    a_func()""")
    check_fp(src, 5, 5)
    assert [d.name for d in jedi.Script(src).goto_definitions()] == ['int']


def test_func_with_for_and_comment():
    # The first newline is important, leave it. It should not trigger another
    # parser split.
    src = dedent("""\

    def func():
        pass

    for a in [1]:
        # COMMENT
        a""")
    check_fp(src, 2)
    check_fp('a\n' + src, 1, 3)


def test_incomplete_function():
    source = '''return ImportErr'''

    script = jedi.Script(dedent(source), 1, 3)
    assert script.completions()
