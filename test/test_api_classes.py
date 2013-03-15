import pytest

from jedi import api


def make_definitions():
    return api.defined_names("""
    import sys

    class C:
        pass

    x = C()

    def f():
        pass
    """)


@pytest.mark.parametrize('definition', make_definitions())
def test_basedefinition_type(definition):
    assert definition.type in ('module', 'class', 'instance', 'function',
                               'statement', 'import')
