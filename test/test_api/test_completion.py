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


def test_in_empty_space():
    code = dedent('''\
    class X(object):
        def __init__(self):
            hello
            ''')
    comps = Script(code, 3, 7).completions()
    self, = [c for c in comps if c.name == 'self']
    assert self.name == 'self'
    def_, = self._goto_definitions()
    assert def_.name == 'X'
