from textwrap import dedent

import pytest

import jedi
from jedi._compatibility import u
from jedi import cache
from jedi.parser import load_grammar
from jedi.parser.fast import FastParser
from jedi.parser.utils import save_parser


def test_add_to_end():
    """
    fast_parser doesn't parse everything again. It just updates with the
    help of caches, this is an example that didn't work.
    """

    a = dedent("""\
    class Abc():
        def abc(self):
            self.x = 3

    class Two(Abc):
        def g(self):
            self
    """)      # ^ here is the first completion

    b = "    def h(self):\n" \
        "        self."
    assert jedi.Script(a, 7, 12, 'example.py').completions()
    assert jedi.Script(a + b, path='example.py').completions()

    a = a[:-1] + '.\n'
    assert jedi.Script(a, 7, 13, 'example.py').completions()
    assert jedi.Script(a + b, path='example.py').completions()


def test_split_parts():
    cache.parser_cache.pop(None, None)

    def splits(source):
        class Mock(FastParser):
            def __init__(self, *args):
                self.number_of_splits = 0

        return tuple(FastParser._split_parts(Mock(None, None), source))

    def test(*parts):
        assert splits(''.join(parts)) == parts

    test('a\n\n', 'def b(): pass\n', 'c\n')
    test('a\n', 'def b():\n pass\n', 'c\n')

    test('from x\\\n')
    test('a\n\\\n')


def check_fp(src, number_parsers_used, number_of_splits=None, number_of_misses=0):
    if number_of_splits is None:
        number_of_splits = number_parsers_used

    p = FastParser(load_grammar(), u(src))
    save_parser(None, p, pickling=False)

    assert src == p.module.get_code()
    assert p.number_of_splits == number_of_splits
    assert p.number_parsers_used == number_parsers_used
    assert p.number_of_misses == number_of_misses
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


def test_if_simple():
    src = dedent('''\
    if 1:
        a = 3
    ''')
    check_fp(src + 'a', 1)
    check_fp(src + "else:\n    a = ''\na", 1)


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
    # We don't need to parse the for loop, but we need to parse the other two,
    # because the split is in a different place.
    check_fp('a\n' + src, 2, 3)


def test_one_statement_func():
    src = dedent("""\
    first
    def func(): a
    """)
    check_fp(src + 'second', 3)
    # Empty the parser cache, because we're not interested in modifications
    # here.
    cache.parser_cache.pop(None, None)
    check_fp(src + 'def second():\n a', 3)


def test_for_on_one_line():
    src = dedent("""\
    foo = 1
    for x in foo: pass

    def hi():
        pass
    """)
    check_fp(src, 2)

    src = dedent("""\
    def hi():
        for x in foo: pass
        pass

    pass
    """)
    check_fp(src, 2)

    src = dedent("""\
    def hi():
        for x in foo: pass

        def nested():
            pass
    """)
    check_fp(src, 2)


def test_open_parentheses():
    func = 'def func():\n a'
    code = u('isinstance(\n\n' + func)
    p = FastParser(load_grammar(), code)
    # As you can see, the part that was failing is still there in the get_code
    # call. It is not relevant for evaluation, but still available as an
    # ErrorNode.
    assert p.module.get_code() == code
    assert p.number_of_splits == 2
    assert p.number_parsers_used == 2
    save_parser(None, p, pickling=False)

    # Now with a correct parser it should work perfectly well.
    check_fp('isinstance()\n' + func, 1, 2)


def test_backslash():
    src = dedent(r"""
    a = 1\
        if 1 else 2
    def x():
        pass
    """)
    check_fp(src, 2)

    src = dedent(r"""
    def x():
        a = 1\
    if 1 else 2
        def y():
            pass
    """)
    # The dangling if leads to not splitting where we theoretically could
    # split.
    check_fp(src, 2)

    src = dedent(r"""
    def first():
        if foo \
                and bar \
                or baz:
            pass
    def second():
        pass
    """)
    check_fp(src, 2)
