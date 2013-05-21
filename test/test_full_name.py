"""
Tests for :attr:`.BaseDefinition.full_name`.

There are three kinds of test:

#. Test classes derived from :class:`MixinTestFullName`.
   Child class defines :meth:`.get_definitions` to alter how
   the api definition instance is created.

#. :class:`TestFullDefinedName` is to test combination of
   :attr:`.full_name` and :func:`.defined_names`.

#. Misc single-function tests.

"""

import textwrap

import jedi
from jedi import api_classes
from .base import TestBase


class MixinTestFullName(object):

    def get_definitions(self, source):
        """
        Get definition objects of the variable at the end of `source`.
        """
        raise NotImplementedError

    def check(self, source, desired):
        definitions = self.get_definitions(textwrap.dedent(source))
        self.assertEqual(definitions[0].full_name, desired)

    def test_os_path_join(self):
        self.check('import os; os.path.join', 'os.path.join')

    def test_builtin(self):
        self.check('type', 'type')

    def test_from_import(self):
        self.check('from os import path', 'os.path')


class TestFullNameWithGotoDefinitions(MixinTestFullName, TestBase):

    get_definitions = TestBase.goto_definitions

    def test_tuple_mapping(self):
        self.check("""
        import re
        any_re = re.compile('.*')
        any_re""", 're.RegexObject')


class TestFullNameWithCompletions(MixinTestFullName, TestBase):
    get_definitions = TestBase.completions


class TestFullDefinedName(TestBase):

    """
    Test combination of :attr:`.full_name` and :func:`.defined_names`.
    """

    def check(self, source, desired):
        definitions = jedi.defined_names(textwrap.dedent(source))
        full_names = [d.full_name for d in definitions]
        self.assertEqual(full_names, desired)

    def test_local_names(self):
        self.check("""
        def f(): pass
        class C: pass
        """, ['f', 'C'])

    def test_imports(self):
        self.check("""
        import os
        from os import path
        from os.path import join
        from os import path as opath
        """, ['os', 'os.path', 'os.path.join', 'os.path'])


def test_keyword_full_name_should_be_none():
    """issue #94"""
    # Using `from jedi.keywords import Keyword` here does NOT work
    # in Python 3.  This is due to the import hack jedi using.
    Keyword = api_classes.keywords.Keyword
    d = api_classes.Definition(Keyword('(', (0, 0)))
    assert d.full_name is None
