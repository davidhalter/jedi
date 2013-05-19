"""
Tests for `api.defined_names`.
"""

from jedi import api
from .base import TestBase


class TestDefinedNames(TestBase):

    def test_get_definitions_flat(self):
        definitions = api.defined_names("""
        import module
        class Class:
            pass
        def func():
            pass
        data = None
        """)
        self.assertEqual([d.name for d in definitions],
                         ['module', 'Class', 'func', 'data'])

    def test_dotted_assignment(self):
        definitions = api.defined_names("""
        x = Class()
        x.y.z = None
        """)
        self.assertEqual([d.name for d in definitions],
                         ['x'])

    def test_multiple_assignment(self):
        definitions = api.defined_names("""
        x = y = None
        """)
        self.assertEqual([d.name for d in definitions],
                         ['x', 'y'])

    def test_multiple_imports(self):
        definitions = api.defined_names("""
        from module import a, b
        from another_module import *
        """)
        self.assertEqual([d.name for d in definitions],
                         ['a', 'b'])

    def test_nested_definitions(self):
        definitions = api.defined_names("""
        class Class:
            def f():
                pass
            def g():
                pass
        """)
        self.assertEqual([d.name for d in definitions],
                         ['Class'])
        subdefinitions = definitions[0].defined_names()
        self.assertEqual([d.name for d in subdefinitions],
                         ['f', 'g'])
        self.assertEqual([d.full_name for d in subdefinitions],
                         ['Class.f', 'Class.g'])
