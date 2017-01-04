from textwrap import dedent
from jedi import Script


def test_in_whitespace():
    code = dedent('''
    def x():
        pass''')
    assert len(Script(code, column=2).completions()) > 20


def test_empty_init():
    """This was actually an issue."""
    code = dedent('''\
    class X(object): pass
    X(''')
    assert Script(code).completions()
