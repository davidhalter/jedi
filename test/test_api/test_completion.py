import os
import sys
from textwrap import dedent


def test_in_whitespace(Script):
    code = dedent('''
    def x():
        pass''')
    assert len(Script(code, column=2).completions()) > 20


def test_empty_init(Script):
    """This was actually an issue."""
    code = dedent('''\
    class X(object): pass
    X(''')
    assert Script(code).completions()


def test_in_empty_space(Script):
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


def test_indent_context(Script):
    """
    If an INDENT is the next supposed token, we should still be able to
    complete.
    """
    code = 'if 1:\nisinstanc'
    comp, = Script(code).completions()
    assert comp.name == 'isinstance'


def test_keyword_context(Script):
    def get_names(*args, **kwargs):
        return [d.name for d in Script(*args, **kwargs).completions()]

    names = get_names('if 1:\n pass\n')
    assert 'if' in names
    assert 'elif' in names


def test_os_nowait(Script):
    """ github issue #45 """
    s = Script("import os; os.P_").completions()
    assert 'P_NOWAIT' in [i.name for i in s]


def test_points_in_completion(Script):
    """At some point, points were inserted into the completions, this
    caused problems, sometimes.
    """
    c = Script("if IndentationErr").completions()
    assert c[0].name == 'IndentationError'
    assert c[0].complete == 'or'


def test_loading_unicode_files_with_bad_global_charset(Script, monkeypatch, tmpdir):
    dirname = str(tmpdir.mkdir('jedi-test'))
    filename1 = os.path.join(dirname, 'test1.py')
    filename2 = os.path.join(dirname, 'test2.py')
    if sys.version_info < (3, 0):
        data = "# coding: latin-1\nfoo = 'm\xf6p'\n"
    else:
        data = "# coding: latin-1\nfoo = 'm\xf6p'\n".encode("latin-1")

    with open(filename1, "wb") as f:
        f.write(data)
    s = Script("from test1 import foo\nfoo.",
               line=2, column=4, path=filename2)
    s.completions()


def test_fake_subnodes(Script):
    """
    Test the number of subnodes of a fake object.

    There was a bug where the number of child nodes would grow on every
    call to :func:``jedi.evaluate.compiled.fake.get_faked``.

    See Github PR#649 and isseu #591.
    """
    def get_str_completion(values):
        for c in values:
            if c.name == 'str':
                return c
    limit = None
    for i in range(2):
        completions = Script('').completions()
        c = get_str_completion(completions)
        str_context, = c._name.infer()
        n = len(str_context.tree_node.children[-1].children)
        if i == 0:
            limit = n
        else:
            assert n == limit


def test_generator(Script):
    # Did have some problems with the usage of generator completions this
    # way.
    s = "def abc():\n" \
        "    yield 1\n" \
        "abc()."
    assert Script(s).completions()


def test_in_comment(Script):
    assert Script(" # Comment").completions()
    assert Script("max_attr_value = int(2) # Cast to int for spe").completions()
