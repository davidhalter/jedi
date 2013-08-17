""" Test all things related to the ``jedi.api_classes`` module.
"""

import textwrap

import pytest

from jedi import Script
import jedi


def test_is_keyword():
    results = Script('import ', 1, 1, None).goto_definitions()
    assert len(results) == 1 and results[0].is_keyword == True
    results = Script('str', 1, 1, None).goto_definitions()
    assert len(results) == 1 and results[0].is_keyword == False

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
    definitions += jedi.defined_names(source)

    source += textwrap.dedent("""
    variable = sys or C or x or f or g or g() or h""")
    lines = source.splitlines()
    script = Script(source, len(lines), len('variable'), None)
    definitions += script.goto_definitions()

    script2 = Script(source, 4, len('class C'), None)
    definitions += script2.usages()

    source_param = "def f(a): return a"
    script_param = Script(source_param, 1, len(source_param), None)
    definitions += script_param.goto_assignments()

    return definitions


@pytest.mark.parametrize('definition', make_definitions())
def test_basedefinition_type(definition):
    assert definition.type in ('module', 'class', 'instance', 'function',
                               'generator', 'statement', 'import', 'param')


def test_function_call_signature_in_doc():
    defs = Script("""
    def f(x, y=1, z='a'):
        pass
    f""").goto_definitions()
    doc = defs[0].doc
    assert "f(x, y = 1, z = 'a')" in doc

def test_class_call_signature():
    defs = Script("""
    class Foo:
        def __init__(self, x, y=1, z='a'):
            pass
    Foo""").goto_definitions()
    doc = defs[0].doc
    assert "Foo(self, x, y = 1, z = 'a')" in doc


def test_position_none_if_builtin():
    gotos = Script('import sys; sys.path').goto_assignments()
    assert gotos[0].line is None
    assert gotos[0].column is None
