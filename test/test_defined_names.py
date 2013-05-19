"""
Tests for `api.defined_names`.
"""

import textwrap

from jedi import api
from .base import TestBase


class TestDefinedNames(TestBase):

    def check_defined_names(self, source, names):
        definitions = api.defined_names(textwrap.dedent(source))
        self.assertEqual([d.name for d in definitions], names)
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
        """, ['x'])

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
        self.assertEqual([d.name for d in subdefinitions],
                         ['f', 'g'])
        self.assertEqual([d.full_name for d in subdefinitions],
                         ['Class.f', 'Class.g'])
