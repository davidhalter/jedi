from textwrap import dedent

import jedi
import pytest


@pytest.mark.skipif('sys.version_info[0] < 3')
def test_simple_annotations():
    """
    Annotations only exist in Python 3.
    At the moment we ignore them. So they should be parsed and not interfere
    with anything.
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
