from textwrap import dedent

import pytest

import jedi
from jedi import debug
from jedi.common import splitlines
from jedi import cache
from jedi.parser.cache import parser_cache
from jedi.parser.python import load_grammar
from jedi.parser.python.diff import DiffParser
from jedi.parser.python import parse


def _check_error_leaves_nodes(node):
    if node.type in ('error_leaf', 'error_node'):
        return True

    try:
        children = node.children
    except AttributeError:
        pass
    else:
        for child in children:
            if _check_error_leaves_nodes(child):
                return True
    return False


def _assert_valid_graph(node):
    """
    Checks if the parent/children relationship is correct.
    """
    try:
        children = node.children
    except AttributeError:
        return

    for child in children:
        assert child.parent == node
        _assert_valid_graph(child)


class Differ(object):
    grammar = load_grammar()

    def initialize(self, code):
        debug.dbg('differ: initialize', color='YELLOW')
        self.lines = splitlines(code, keepends=True)
        parser_cache.pop(None, None)
        self.module = parse(code, diff_cache=True, cache=True)
        return self.module

    def parse(self, code, copies=0, parsers=0, expect_error_leaves=False):
        debug.dbg('differ: parse copies=%s parsers=%s', copies, parsers, color='YELLOW')
        lines = splitlines(code, keepends=True)
        diff_parser = DiffParser(self.grammar, self.module)
        new_module = diff_parser.update(self.lines, lines)
        self.lines = lines
        assert code == new_module.get_code()
        assert diff_parser._copy_count == copies
        assert diff_parser._parser_count == parsers

        assert expect_error_leaves == _check_error_leaves_nodes(new_module)
        _assert_valid_graph(new_module)
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
    # Same as before parsers should be used at the end, because it doesn't end
    # with newlines and that leads to complications.
    differ.parse(func_before + 'a', copies=1, parsers=1)

    # Now that we have a newline at the end, everything is easier in Python
    # syntax, we can parse once and then get a copy.
    differ.parse(func_before + 'a\n', copies=1, parsers=1)
    differ.parse(func_before + 'a\n', copies=1)

    # Getting rid of an old parser: Still no parsers used.
    differ.parse('a\n', copies=1)
    # Now the file has completely changed and we need to parse.
    differ.parse('b\n', parsers=1)
    # And again.
    differ.parse('a\n', parsers=1)


def test_positions(differ):
    # Empty the parser cache for the path None.
    cache.parser_cache.pop(None, None)

    func_before = 'class A:\n pass\n'
    m = differ.initialize(func_before + 'a')
    assert m.start_pos == (1, 0)
    assert m.end_pos == (3, 1)

    m = differ.parse('a', parsers=1)
    assert m.start_pos == (1, 0)
    assert m.end_pos == (1, 1)

    m = differ.parse('a\n\n', parsers=1)
    assert m.end_pos == (3, 0)
    m = differ.parse('a\n\n ', copies=1, parsers=1)
    assert m.end_pos == (3, 1)
    m = differ.parse('a ', parsers=1)
    assert m.end_pos == (1, 2)


def test_if_simple(differ):
    src = dedent('''\
    if 1:
        a = 3
    ''')
    else_ = "else:\n    a = ''\n"

    differ.initialize(src + 'a')
    differ.parse(src + else_ + "a", copies=0, parsers=1)

    differ.parse(else_, parsers=1, expect_error_leaves=True)
    differ.parse(src + else_, parsers=1)


def test_func_with_for_and_comment(differ):
    # The first newline is important, leave it. It should not trigger another
    # parser split.
    src = dedent("""\

    def func():
        pass


    for a in [1]:
        # COMMENT
        a""")
    differ.initialize(src)
    differ.parse('a\n' + src, copies=1, parsers=2)


def test_one_statement_func(differ):
    src = dedent("""\
    first
    def func(): a
    """)
    differ.initialize(src + 'second')
    differ.parse(src + 'def second():\n a', parsers=1, copies=1)


def test_for_on_one_line(differ):
    src = dedent("""\
    foo = 1
    for x in foo: pass

    def hi():
        pass
    """)
    differ.initialize(src)

    src = dedent("""\
    def hi():
        for x in foo: pass
        pass

    pass
    """)
    differ.parse(src, parsers=2)

    src = dedent("""\
    def hi():
        for x in foo: pass
        pass

        def nested():
            pass
    """)
    # The second parser is for parsing the `def nested()` which is an `equal`
    # operation in the SequenceMatcher.
    differ.parse(src, parsers=1, copies=1)


def test_open_parentheses(differ):
    func = 'def func():\n a\n'
    code = 'isinstance(\n\n' + func
    new_code = 'isinstance(\n' + func
    differ.initialize(code)

    differ.parse(new_code, parsers=1, expect_error_leaves=True)

    new_code = 'a = 1\n' + new_code
    differ.parse(new_code, copies=1, parsers=1, expect_error_leaves=True)

    func += 'def other_func():\n pass\n'
    differ.initialize('isinstance(\n' + func)
    # Cannot copy all, because the prefix of the function is once a newline and
    # once not.
    differ.parse('isinstance()\n' + func, parsers=2, copies=1)


def test_open_parentheses_at_end(differ):
    code = "a['"
    differ.initialize(code)
    differ.parse(code, parsers=1, expect_error_leaves=True)

def test_backslash(differ):
    src = dedent(r"""
    a = 1\
        if 1 else 2
    def x():
        pass
    """)
    differ.initialize(src)

    src = dedent(r"""
    def x():
        a = 1\
    if 1 else 2
        def y():
            pass
    """)
    differ.parse(src, parsers=2)

    src = dedent(r"""
    def first():
        if foo \
                and bar \
                or baz:
            pass
    def second():
        pass
    """)
    differ.parse(src, parsers=1)


def test_full_copy(differ):
    code = 'def foo(bar, baz):\n pass\n bar'
    differ.initialize(code)
    differ.parse(code, copies=1, parsers=1)


def test_wrong_whitespace(differ):
    code = '''
    hello
    '''
    differ.initialize(code)
    differ.parse(code + 'bar\n    ', parsers=1, copies=1)

    code += """abc(\npass\n    """
    differ.parse(code, parsers=1, copies=1, expect_error_leaves=True)


def test_issues_with_error_leaves(differ):
    code = dedent('''
    def ints():
        str..
        str
    ''')
    code2 = dedent('''
    def ints():
        str.
        str
    ''')
    differ.initialize(code)
    differ.parse(code2, parsers=1, copies=1, expect_error_leaves=True)


def test_unfinished_nodes(differ):
    code = dedent('''
    class a():
        def __init__(self, a):
            self.a =  a
        def p(self):
    a(1)
    ''')
    code2 = dedent('''
    class a():
        def __init__(self, a):
            self.a =  a
        def p(self):
            self
    a(1)
    ''')
    differ.initialize(code)
    differ.parse(code2, parsers=1, copies=2)


def test_nested_if_and_scopes(differ):
    code = dedent('''
    class a():
        if 1:
            def b():
                2
    ''')
    code2 = code + '    else:\n        3'
    differ.initialize(code)
    differ.parse(code2, parsers=1, copies=0)


def test_word_before_def(differ):
    code1 = 'blub def x():\n'
    code2 = code1 + ' s'
    differ.initialize(code1)
    differ.parse(code2, parsers=1, copies=0, expect_error_leaves=True)


def test_classes_with_error_leaves(differ):
    code1 = dedent('''
        class X():
            def x(self):
                blablabla
                assert 3
                self.

        class Y():
            pass
    ''')
    code2 = dedent('''
        class X():
            def x(self):
                blablabla
                assert 3
                str(

        class Y():
            pass
    ''')

    differ.initialize(code1)
    differ.parse(code2, parsers=2, copies=1, expect_error_leaves=True)


def test_totally_wrong_whitespace(differ):
    code1 = '''
        class X():
            raise n

        class Y():
            pass
    '''
    code2 = '''
        class X():
            raise n
            str(

        class Y():
            pass
    '''

    differ.initialize(code1)
    differ.parse(code2, parsers=3, copies=1, expect_error_leaves=True)


def test_node_insertion(differ):
    code1 = dedent('''
        class X():
            def y(self):
                a = 1
                b = 2

                c = 3
                d = 4
    ''')
    code2 = dedent('''
        class X():
            def y(self):
                a = 1
                b = 2
                str

                c = 3
                d = 4
    ''')

    differ.initialize(code1)
    differ.parse(code2, parsers=1, copies=2)


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

    def complete(code, line=None, column=None):
        script = jedi.Script(code, line, column, 'example.py')
        assert script.completions()
        _assert_valid_graph(script._get_module())

    complete(a, 7, 12)
    complete(a + b)

    a = a[:-1] + '.\n'
    complete(a, 7, 13)
    complete(a + b)


def test_whitespace_at_end(differ):
    code = dedent('str\n\n')

    differ.initialize(code)
    differ.parse(code + '\n', parsers=1, copies=1)


def test_endless_while_loop(differ):
    """
    This was a bug in Jedi #878.
    """
    code = '#dead'
    differ.initialize(code)
    module = differ.parse(code, parsers=1)
    assert module.end_pos == (1, 5)

    code = '#dead\n'
    differ.initialize(code)
    module = differ.parse(code + '\n', parsers=1)
    assert module.end_pos == (3, 0)


def test_in_class_movements(differ):
    code1 = dedent("""\
        class PlaybookExecutor:
            p
            b
            def run(self):
                1
                try:
                    x
                except:
                    pass
    """)
    code2 = dedent("""\
        class PlaybookExecutor:
            b
            def run(self):
                1
                try:
                    x
                except:
                    pass
    """)

    differ.initialize(code1)
    differ.parse(code2, parsers=2, copies=1)


def test_in_parentheses_newlines(differ):
    code1 = dedent("""
    x = str(
        True)

    a = 1

    def foo():
        pass

    b = 2""")

    code2 = dedent("""
    x = str(True)

    a = 1

    def foo():
        pass

    b = 2""")


    differ.initialize(code1)
    differ.parse(code2, parsers=2, copies=1)
    differ.parse(code1, parsers=2, copies=1)
