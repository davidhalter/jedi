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

    def g():
        yield

    h = lambda: None
    """)

    definitions = []
    definitions += api.defined_names(source)

    source += textwrap.dedent("""
    variable = sys or C or x or f or g or g() or h""")
    lines = source.splitlines()
    script = api.Script(source, len(lines), len('variable'), None)
    definitions += script.goto_definitions()

    script2 = api.Script(source, 4, len('class C'), None)
    definitions += script2.usages()

    source_param = "def f(a): return a"
    script_param = api.Script(source_param, 1, len(source_param), None)
    definitions += script_param.goto_assignments()

    return definitions


@pytest.mark.parametrize('definition', make_definitions())
def test_basedefinition_type(definition):
    assert definition.type in ('module', 'class', 'instance', 'function',
                               'generator', 'statement', 'import', 'param')
