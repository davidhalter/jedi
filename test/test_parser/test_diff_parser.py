from textwrap import dedent

import pytest

import jedi
from jedi._compatibility import u
from jedi.common import splitlines
from jedi import cache
from jedi.parser import load_grammar
from jedi.parser.fast import FastParser, DiffParser
from jedi.parser import ParserWithRecovery
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


class Differ(object):
    def __init__(self):
        self._first_use = True

    def initialize(self, source):
        grammar = load_grammar()
        self.parser = ParserWithRecovery(grammar, source)
        return self.parser.module

    def parse(self, source, copies=0, parsers=0):
        lines = splitlines(source, keepends=True)
        diff_parser = DiffParser(self.parser)
        new_module = diff_parser.update(lines)
        assert source == new_module.get_code()
        assert diff_parser._copy_count == copies
        assert diff_parser._parser_count == parsers
        self.parser.module = new_module
        return new_module


@pytest.fixture()
def differ():
    return Differ()


def test_change_and_undo(differ):
    # Empty the parser cache for the path None.
    cache.parser_cache.pop(None, None)
    func_before = 'def func():\n    pass\n'
    # Parse the function and a.
    differ.initialize(func_before + 'a')
    # Parse just b.
    differ.parse(func_before + 'b', copies=1, parsers=1)
    # b has changed to a again, so parse that.
    differ.parse(func_before + 'a', copies=1, parsers=1)
    # Same as before no parsers should be used.
    differ.parse(func_before + 'a', copies=1)

    # Getting rid of an old parser: Still no parsers used.
    differ.parse('a', copies=1)
    # Now the file has completely changed and we need to parse.
    differ.parse('b', parsers=1)
    # And again.
    differ.parse('a', parsers=1)


def test_positions(differ):
    # Empty the parser cache for the path None.
    cache.parser_cache.pop(None, None)

    func_before = 'class A:\n pass\n'
    m = differ.initialize(func_before + 'a')
    assert m.start_pos == (1, 0)
    assert m.end_pos == (3, 1)

    m = differ.parse('a', copies=1)
    assert m.start_pos == (1, 0)
    assert m.end_pos == (1, 1)

    m = differ.parse('a\n\n', parsers=1)
    assert m.end_pos == (3, 0)
    m = differ.parse('a\n\n ', copies=1, parsers=1)
    assert m.end_pos == (3, 1)
    m = differ.parse('a ', parsers=1)
    assert m.end_pos == (1, 2)


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
