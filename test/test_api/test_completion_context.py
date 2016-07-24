from textwrap import dedent
from jedi import Script


def test_in_whitespace():
    code = dedent('''
    def x():
        pass''')
    assert len(Script(code, column=2).completions()) > 20
