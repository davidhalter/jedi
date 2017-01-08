import pytest

import jedi
from jedi._compatibility import py_version


def _eval_literal(value):
    def_, = jedi.Script(value).goto_definitions()
    return def_._name._context


@pytest.mark.skipif('sys.version_info[:2] < (3, 6)')
def test_f_strings():
    """
    f literals are not really supported in Jedi. They just get ignored and an
    empty string is returned.
    """
    context = _eval_literal('f"asdf"')
    assert context.obj == ''
    context = _eval_literal('f"{asdf}"')
    assert context.obj == ''
    context = _eval_literal('F"{asdf}"')
    assert context.obj == ''
    context = _eval_literal('rF"{asdf}"')
    assert context.obj == ''


def test_rb_strings():
    context = _eval_literal('br"asdf"')
    assert context.obj == b'asdf'
    context = _eval_literal('rb"asdf"')
    if py_version < 33:
        # Before Python 3.3 there was a more strict definition in which order
        # you could define literals.
        assert context.obj == ''
    else:
        assert context.obj == b'asdf'
