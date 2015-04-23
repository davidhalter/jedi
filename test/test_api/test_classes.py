""" Test all things related to the ``jedi.api_classes`` module.
"""

from textwrap import dedent
from inspect import cleandoc

import pytest

from jedi import Script, defined_names, __doc__ as jedi_doc, names
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
    assert "f(x, y=1, z='a')" in str(doc)


def test_class_call_signature():
    defs = Script("""
    class Foo:
        def __init__(self, x, y=1, z='a'):
            pass
    Foo""").goto_definitions()
    doc = defs[0].doc
    assert "Foo(self, x, y=1, z='a')" in str(doc)


def test_position_none_if_builtin():
    gotos = Script('import sys; sys.path').goto_assignments()
    assert gotos[0].line is None
    assert gotos[0].column is None


@cwd_at('.')
def test_completion_docstring():
    """
    Jedi should follow imports in certain conditions
    """
    def docstr(src, result):
        c = Script(src).completions()[0]
        assert c.docstring(raw=True, fast=False) == cleandoc(result)

    c = Script('import jedi\njed').completions()[0]
    assert c.docstring(fast=False) == cleandoc(jedi_doc)

    docstr('import jedi\njedi.Scr', cleandoc(Script.__doc__))

    docstr('abcd=3;abcd', '')
    docstr('"hello"\nabcd=3\nabcd', 'hello')
    # It works with a ; as well.
    docstr('"hello"\nabcd=3;abcd', 'hello')
    # Shouldn't work with a tuple.
    docstr('"hello",0\nabcd=3\nabcd', '')


def test_completion_params():
    c = Script('import string; string.capwords').completions()[0]
    assert [p.name for p in c.params] == ['s', 'sep']


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


def test_param_endings():
    """
    Params should be represented without the comma and whitespace they have
    around them.
    """
    sig = Script('def x(a, b=5, c=""): pass\n x(').call_signatures()[0]
    assert [p.description for p in sig.params] == ['a', 'b=5', 'c=""']


class TestIsDefinition(TestCase):
    def _def(self, source, index=-1):
        return names(dedent(source), references=True, all_scopes=True)[index]

    def _bool_is_definitions(self, source):
        ns = names(dedent(source), references=True, all_scopes=True)
        # Assure that names are definitely sorted.
        ns = sorted(ns, key=lambda name: (name.line, name.column))
        return [name.is_definition() for name in ns]

    def test_name(self):
        d = self._def('name')
        assert d.name == 'name'
        assert not d.is_definition()

    def test_stmt(self):
        src = 'a = f(x)'
        d = self._def(src, 0)
        assert d.name == 'a'
        assert d.is_definition()
        d = self._def(src, 1)
        assert d.name == 'f'
        assert not d.is_definition()
        d = self._def(src)
        assert d.name == 'x'
        assert not d.is_definition()

    def test_import(self):
        assert self._bool_is_definitions('import x as a') == [False, True]
        assert self._bool_is_definitions('from x import y') == [False, True]
        assert self._bool_is_definitions('from x.z import y') == [False, False, True]


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
        assert parent.name == ''
        assert parent.type == 'module'

    def test_parent_on_completion(self):
        parent = Script(dedent('''\
            class Foo():
                def bar(): pass
            Foo().bar''')).completions()[0].parent()
        assert parent.name == 'Foo'
        assert parent.type == 'instance'

        parent = Script('str.join').completions()[0].parent()
        assert parent.name == 'str'
        assert parent.type == 'class'


def test_type():
    """
    Github issue #397, type should never raise an error.
    """
    for c in Script('import os; os.path.').completions():
        assert c.type


class TestGotoAssignments(TestCase):
    """
    This tests the BaseDefinition.goto_assignments function, not the jedi
    function. They are not really different in functionality, but really
    different as an implementation.
    """
    def test_repetition(self):
        defs = names('a = 1; a', references=True, definitions=False)
        # Repeat on the same variable. Shouldn't change once we're on a
        # definition.
        for _ in range(3):
            assert len(defs) == 1
            ass = defs[0].goto_assignments()
            assert ass[0].description == 'a = 1'

    def test_named_params(self):
        src = """\
                def foo(a=1, bar=2):
                    pass
                foo(bar=1)
              """
        bar = names(dedent(src), references=True)[-1]
        param = bar.goto_assignments()[0]
        assert param.start_pos == (1, 13)
        assert param.type == 'param'

    def test_class_call(self):
        src = 'from threading import Thread; Thread(group=1)'
        n = names(src, references=True)[-1]
        assert n.name == 'group'
        param_def = n.goto_assignments()[0]
        assert param_def.name == 'group'
        assert param_def.type == 'param'

    def test_parentheses(self):
        n = names('("").upper', references=True)[-1]
        assert n.goto_assignments()[0].name == 'upper'

    def test_import(self):
        nms = names('from json import load', references=True)
        assert nms[0].name == 'json'
        assert nms[0].type == 'import'
        n = nms[0].goto_assignments()[0]
        assert n.name == 'json'
        assert n.type == 'module'

        assert nms[1].name == 'load'
        assert nms[1].type == 'import'
        n = nms[1].goto_assignments()[0]
        assert n.name == 'load'
        assert n.type == 'function'

        nms = names('import os; os.path', references=True)
        assert nms[0].name == 'os'
        assert nms[0].type == 'import'
        n = nms[0].goto_assignments()[0]
        assert n.name == 'os'
        assert n.type == 'module'

        n = nms[2].goto_assignments()[0]
        assert n.name == 'path'
        assert n.type == 'import'

        nms = names('import os.path', references=True)
        n = nms[0].goto_assignments()[0]
        assert n.name == 'os'
        assert n.type == 'module'
        n = nms[1].goto_assignments()[0]
        # This is very special, normally the name doesn't chance, but since
        # os.path is a sys.modules hack, it does.
        assert n.name in ('ntpath', 'posixpath')
        assert n.type == 'module'

    def test_import_alias(self):
        nms = names('import json as foo', references=True)
        assert nms[0].name == 'json'
        assert nms[0].type == 'import'
        n = nms[0].goto_assignments()[0]
        assert n.name == 'json'
        assert n.type == 'module'

        assert nms[1].name == 'foo'
        assert nms[1].type == 'import'
        ass = nms[1].goto_assignments()
        assert len(ass) == 1
        assert ass[0].name == 'json'
        assert ass[0].type == 'module'
