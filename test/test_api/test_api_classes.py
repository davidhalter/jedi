""" Test all things related to the ``jedi.api_classes`` module.
"""

from textwrap import dedent
from inspect import cleandoc

import pytest

from jedi import Script, defined_names, __doc__ as jedi_doc
from jedi.parser import representation as pr
from ..helpers import cwd_at
from ..helpers import TestCase


def test_is_keyword():
    #results = Script('import ', 1, 1, None).goto_definitions()
    #assert len(results) == 1 and results[0].is_keyword is True
    results = Script('str', 1, 1, None).goto_definitions()
    assert len(results) == 1 and results[0].is_keyword is False


def make_definitions():
    """
    Return a list of definitions for parametrized tests.

    :rtype: [jedi.api_classes.BaseDefinition]
    """
    source = dedent("""
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
    definitions += defined_names(source)

    source += dedent("""
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


def test_basedefinition_type_import():
    def get_types(source, **kwargs):
        return set([t.type for t in Script(source, **kwargs).completions()])

    # import one level
    assert get_types('import t') == set(['module'])
    assert get_types('import ') == set(['module'])
    assert get_types('import datetime; datetime') == set(['module'])

    # from
    assert get_types('from datetime import timedelta') == set(['class'])
    assert get_types('from datetime import timedelta; timedelta') == set(['class'])
    assert get_types('from json import tool') == set(['module'])
    assert get_types('from json import tool; tool') == set(['module'])

    # import two levels
    assert get_types('import json.tool; json') == set(['module'])
    assert get_types('import json.tool; json.tool') == set(['module'])
    assert get_types('import json.tool; json.tool.main') == set(['function'])
    assert get_types('import json.tool') == set(['module'])
    assert get_types('import json.tool', column=9) == set(['module'])


def test_function_call_signature_in_doc():
    defs = Script("""
    def f(x, y=1, z='a'):
        pass
    f""").goto_definitions()
    doc = defs[0].doc
    assert "f(x, y = 1, z = 'a')" in str(doc)


def test_class_call_signature():
    defs = Script("""
    class Foo:
        def __init__(self, x, y=1, z='a'):
            pass
    Foo""").goto_definitions()
    doc = defs[0].doc
    assert "Foo(self, x, y = 1, z = 'a')" in str(doc)


def test_position_none_if_builtin():
    gotos = Script('import sys; sys.path').goto_assignments()
    assert gotos[0].line is None
    assert gotos[0].column is None


@cwd_at('.')
def test_completion_docstring():
    """
    Jedi should follow imports in certain conditions
    """
    c = Script('import jedi\njed').completions()[0]
    assert c.docstring(fast=False) == cleandoc(jedi_doc)

    c = Script('import jedi\njedi.Scr').completions()[0]
    assert c.docstring(raw=True, fast=False) == cleandoc(Script.__doc__)


def test_signature_params():
    def check(defs):
        params = defs[0].params
        assert len(params) == 1
        assert params[0].name == 'bar'

    s = dedent('''
    def foo(bar):
        pass
    foo''')

    check(Script(s).goto_definitions())

    check(Script(s).goto_assignments())
    check(Script(s + '\nbar=foo\nbar').goto_assignments())


class TestParent(TestCase):
    def _parent(self, source, line=None, column=None):
        defs = Script(dedent(source), line, column).goto_assignments()
        assert len(defs) == 1
        return defs[0].parent()

    def test_parent(self):
        parent = self._parent('foo=1\nfoo')
        assert parent.type == 'module'

        parent = self._parent('''
            def spam():
                if 1:
                    y=1
                    y''')
        assert parent.name == 'spam'
        assert parent.parent().type == 'module'

    def test_on_function(self):
        parent = self._parent('''\
            def spam():
                pass''', 1, len('def spam'))
        assert parent.name == 'spam'
        assert parent.parent().type == 'module'

    def test_parent_on_completion(self):
        parent = Script(dedent('''\
            class Foo():
                def bar(): pass
            Foo().bar''')).completions()[0].parent()
        assert parent.name == 'Foo'
        assert parent.type == 'class'

        parent = Script('str.join').completions()[0].parent()
        assert parent.name == 'str'
        assert parent.type == 'class'


def test_type():
    """
    Github issue #397, type should never raise an error.
    """
    for c in Script('import os; os.path.').completions():
        assert c.type
