import textwrap

import pytest

from jedi import api


def make_definitions():
    """
    Return a list of definitions for parametrized tests.

    :rtype: [jedi.api_classes.BaseDefinition]
    """
    source = textwrap.dedent("""
    import sys

    class C:
        pass

    x = C()

    def f():
        pass
    """)

    definitions = []
    definitions += api.defined_names(source)

    source += textwrap.dedent("""
    variable = sys or C or x or f""")
    lines = source.splitlines()
    script = api.Script(source, len(lines), len('variable'), None)
    definitions += script.definition()

    script2 = api.Script(source, 4, len('class C'), None)
    definitions += script2.related_names()

    return definitions


@pytest.mark.parametrize('definition', make_definitions())
def test_basedefinition_type(definition):
    assert definition.type in ('module', 'class', 'instance', 'function',
                               'statement', 'import')
