from textwrap import dedent

import pytest


def test_simple_annotations(Script, environment):
    """
    Annotations only exist in Python 3.
    If annotations adhere to PEP-0484, we use them (they override inference),
    else they are parsed but ignored
    """
    if environment.version_info.major == 2:
        pytest.skip()

    source = dedent("""\
    def annot(a:3):
        return a

    annot('')""")

    assert [d.name for d in Script(source).goto_definitions()] == ['str']

    source = dedent("""\

    def annot_ret(a:3) -> 3:
        return a

    annot_ret('')""")
    assert [d.name for d in Script(source).goto_definitions()] == ['str']

    source = dedent("""\
    def annot(a:int):
        return a

    annot('')""")

    assert [d.name for d in Script(source).goto_definitions()] == ['int']


@pytest.mark.parametrize('reference', [
    'assert 1',
    '1',
    'def x(): pass',
    '1, 2',
    r'1\n'
])
def test_illegal_forward_references(Script, environment, reference):
    if environment.version_info.major == 2:
        pytest.skip()

    source = 'def foo(bar: "%s"): bar' % reference

    assert not Script(source).goto_definitions()


def test_lambda_forward_references(Script, environment):
    if environment.version_info.major == 2:
        pytest.skip()

    source = 'def foo(bar: "lambda: 3"): bar'

    # For now just receiving the 3 is ok. I'm doubting that this is what we
    # want. We also execute functions. Should we only execute classes?
    assert Script(source).goto_definitions()
