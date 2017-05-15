from textwrap import dedent

from jedi.parser.python import parse
import jedi


def test_form_feed_characters():
    s = "\f\nclass Test(object):\n    pass"
    jedi.Script(s, line=2, column=18).call_signatures()


def check_p(src):
    module_node = parse(src)
    assert src == module_node.get_code()
    return module_node


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
    check_p(src)
    assert [d.name for d in jedi.Script(src, 8, 6).goto_definitions()] == ['int']


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
    check_p(src)
    assert [d.name for d in jedi.Script(src).goto_definitions()] == ['int']


