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
