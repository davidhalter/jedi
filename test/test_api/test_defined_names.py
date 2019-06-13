"""
Tests for `api.defined_names`.
"""

from textwrap import dedent

import pytest

from jedi import names
from ..helpers import TestCase


class TestDefinedNames(TestCase):
    @pytest.fixture(autouse=True)
    def init(self, environment):
        self.environment = environment

    def assert_definition_names(self, definitions, names_):
        assert [d.name for d in definitions] == names_

    def check_defined_names(self, source, names_):
        definitions = names(dedent(source), environment=self.environment)
        self.assert_definition_names(definitions, names_)
        return definitions

    def test_get_definitions_flat(self):
        self.check_defined_names("""
        import module
        class Class:
            pass
        def func():
            pass
        data = None
        """, ['module', 'Class', 'func', 'data'])

    def test_dotted_assignment(self):
        self.check_defined_names("""
        x = Class()
        x.y.z = None
        """, ['x', 'z'])  # TODO is this behavior what we want?

    def test_multiple_assignment(self):
        self.check_defined_names("""
        x = y = None
        """, ['x', 'y'])

    def test_multiple_imports(self):
        self.check_defined_names("""
        from module import a, b
        from another_module import *
        """, ['a', 'b'])

    def test_nested_definitions(self):
        definitions = self.check_defined_names("""
        class Class:
            def f():
                pass
            def g():
                pass
        """, ['Class'])
        subdefinitions = definitions[0].defined_names()
        self.assert_definition_names(subdefinitions, ['f', 'g'])
        self.assertEqual([d.full_name for d in subdefinitions],
                         ['__main__.Class.f', '__main__.Class.g'])

    def test_nested_class(self):
        definitions = self.check_defined_names("""
        class L1:
            class L2:
                class L3:
                    def f(): pass
                def f(): pass
            def f(): pass
        def f(): pass
        """, ['L1', 'f'])
        subdefs = definitions[0].defined_names()
        subsubdefs = subdefs[0].defined_names()
        self.assert_definition_names(subdefs, ['L2', 'f'])
        self.assert_definition_names(subsubdefs, ['L3', 'f'])
        self.assert_definition_names(subsubdefs[0].defined_names(), ['f'])

    def test_class_fields_with_all_scopes_false(self):
        definitions = self.check_defined_names("""
        from module import f
        g = f(f)
        class C:
            h = g

        def foo(x=a):
           bar = x
           return bar
        """, ['f', 'g', 'C', 'foo'])
        C_subdefs = definitions[-2].defined_names()
        foo_subdefs = definitions[-1].defined_names()
        self.assert_definition_names(C_subdefs, ['h'])
        self.assert_definition_names(foo_subdefs, ['x', 'bar'])

    def test_async_stmt_with_all_scopes_false(self):
        definitions = self.check_defined_names("""
        from module import f
        import asyncio

        g = f(f)
        class C:
            h = g
            def __init__(self):
                pass

            async def __aenter__(self):
                pass

        def foo(x=a):
           bar = x
           return bar

        async def async_foo(duration):
            async def wait():
                await asyncio.sleep(100)
            for i in range(duration//100):
                await wait()
            return duration//100*100

        async with C() as cinst:
            d = cinst
        """, ['f', 'asyncio', 'g', 'C', 'foo', 'async_foo', 'cinst', 'd'])
        C_subdefs = definitions[3].defined_names()
        foo_subdefs = definitions[4].defined_names()
        async_foo_subdefs = definitions[5].defined_names()
        cinst_subdefs = definitions[6].defined_names()
        self.assert_definition_names(C_subdefs, ['h', '__init__', '__aenter__'])
        self.assert_definition_names(foo_subdefs, ['x', 'bar'])
        self.assert_definition_names(async_foo_subdefs, ['duration', 'wait', 'i'])
        # We treat d as a name outside `async with` block
        self.assert_definition_names(cinst_subdefs, [])

def test_follow_imports(environment):
    # github issue #344
    imp = names('import datetime', environment=environment)[0]
    assert imp.name == 'datetime'
    datetime_names = [str(d.name) for d in imp.defined_names()]
    assert 'timedelta' in datetime_names


def test_names_twice(environment):
    source = dedent('''
    def lol():
        pass
    ''')

    defs = names(source=source, environment=environment)
    assert defs[0].defined_names() == []


def test_simple_name(environment):
    defs = names('foo', references=True, environment=environment)
    assert not defs[0]._name.infer()


def test_no_error(environment):
    code = dedent("""
        def foo(a, b):
            if a == 10:
                if b is None:
                    print("foo")
                a = 20
        """)
    func_name, = names(code)
    a, b, a20 = func_name.defined_names()
    assert a.name == 'a'
    assert b.name == 'b'
    assert a20.name == 'a'
    assert a20.goto_assignments() == [a20]
