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


def test_indent_context():
    """
    If an INDENT is the next supposed token, we should still be able to
    complete.
    """
    code = 'if 1:\nisinstanc'
    comp, = Script(code).completions()
    assert comp.name == 'isinstance'


def test_keyword_context():
    def get_names(*args, **kwargs):
        return [d.name for d in Script(*args, **kwargs).completions()]

    names = get_names('if 1:\n pass\n')
    assert 'if' in names
    assert 'elif' in names
