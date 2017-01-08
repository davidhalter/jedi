import pytest

import jedi
from jedi._compatibility import py_version


def _eval_literal(value):
    def_, = jedi.Script(value).goto_definitions()
    return def_._name._context.obj


@pytest.mark.skipif('sys.version_info[:2] < (3, 6)')
def test_f_strings():
    """
    f literals are not really supported in Jedi. They just get ignored and an
    empty string is returned.
    """
    assert _eval_literal('f"asdf"') == ''
    assert _eval_literal('f"{asdf}"') == ''
    assert _eval_literal('F"{asdf}"') == ''
    assert _eval_literal('rF"{asdf}"') == ''


def test_rb_strings():
    assert _eval_literal('br"asdf"') == b'asdf'
    obj = _eval_literal('rb"asdf"')
    if py_version < 33:
        # Before Python 3.3 there was a more strict definition in which order
        # you could define literals.
        assert obj == ''
    else:
        assert obj == b'asdf'


@pytest.mark.skipif('sys.version_info[:2] < (3, 6)')
def test_thousand_separators():
    assert _eval_literal('1_2_3') == 123
    assert _eval_literal('123_456_789') == 123456789
    assert _eval_literal('0x3_4') == 52
    assert _eval_literal('0b1_0') == 2
    assert _eval_literal('0o1_0') == 8
