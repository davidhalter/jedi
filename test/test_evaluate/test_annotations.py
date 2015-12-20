from textwrap import dedent

import jedi
import pytest


@pytest.mark.skipif('sys.version_info[0] < 3')
def test_simple_annotations():
    """
    Annotations only exist in Python 3.
    If annotations adhere to PEP-0484, we use them (they override inference),
    else they are parsed but ignored
    """

    source = dedent("""\
    def annot(a:3):
        return a

    annot('')""")

    assert [d.name for d in jedi.Script(source, ).goto_definitions()] == ['str']

    source = dedent("""\

    def annot_ret(a:3) -> 3:
        return a

    annot_ret('')""")
    assert [d.name for d in jedi.Script(source, ).goto_definitions()] == ['str']

    source = dedent("""\
    def annot(a:int):
        return a

    annot('')""")

    assert [d.name for d in jedi.Script(source, ).goto_definitions()] == ['int']


@pytest.mark.skipif('sys.version_info[0] < 3')
@pytest.mark.parametrize('reference', [
    'assert 1',
    '1',
    'def x(): pass',
    '1, 2',
    r'1\n'
])
def test_illegal_forward_references(reference):
    source = 'def foo(bar: "%s"): bar' % reference

    assert not jedi.Script(source).goto_definitions()


@pytest.mark.skipif('sys.version_info[0] < 3')
def test_lambda_forward_references():
    source = 'def foo(bar: "lambda: 3"): bar'

    # For now just receiving the 3 is ok. I'm doubting that this is what we
    # want. We also execute functions. Should we only execute classes?
    assert jedi.Script(source).goto_definitions()
