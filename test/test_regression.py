#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests to avoid errors of the past. Makes use of Python's ``unittest``
module.
"""

import time
import itertools
import os
import textwrap

from .base import TestBase, unittest, cwd_at

import jedi
from jedi import Script
from jedi._compatibility import utf8, unicode
from jedi import api, parsing, common

#jedi.set_debug_function(jedi.debug.print_to_stdout)


class TestRegression(TestBase):
    def test_star_import_cache_duration(self):
        new = 0.01
        old, jedi.settings.star_import_cache_validity = \
                jedi.settings.star_import_cache_validity, new

        cache = api.cache
        cache.star_import_cache = {}  # first empty...
        # path needs to be not-None (otherwise caching effects are not visible)
        jedi.Script('', 1, 0, '').completions()
        time.sleep(2 * new)
        jedi.Script('', 1, 0, '').completions()

        # reset values
        jedi.settings.star_import_cache_validity = old
        length = len(cache.star_import_cache)
        cache.star_import_cache = {}
        self.assertEqual(length, 1)

    def test_goto_definition_cursor(self):

        s = ("class A():\n"
             "    def _something(self):\n"
             "        return\n"
             "    def different_line(self,\n"
             "                   b):\n"
             "        return\n"
             "A._something\n"
             "A.different_line"
             )

        in_name = 2, 9
        under_score = 2, 8
        cls = 2, 7
        should1 = 7, 10
        diff_line = 4, 10
        should2 = 8, 10

        get_def = lambda pos: [d.description for d in self.goto_definitions(s, pos)]
        in_name = get_def(in_name)
        under_score = get_def(under_score)
        should1 = get_def(should1)
        should2 = get_def(should2)

        diff_line = get_def(diff_line)

        assert should1 == in_name
        assert should1 == under_score

        assert should2 == diff_line

        self.assertRaises(jedi.NotFoundError, get_def, cls)

    def test_keyword_doc(self):
        r = list(self.goto_definitions("or", (1, 1)))
        assert len(r) == 1
        assert len(r[0].doc) > 100

        r = list(self.goto_definitions("asfdasfd", (1, 1)))
        assert len(r) == 0

        k = self.completions("fro")[0]
        imp_start = '\nThe ``import'
        assert k.raw_doc.startswith(imp_start)
        assert k.doc.startswith(imp_start)

    def test_operator_doc(self):
        r = list(self.goto_definitions("a == b", (1, 3)))
        assert len(r) == 1
        assert len(r[0].doc) > 100

    def test_function_call_signature(self):
        defs = self.goto_definitions("""
        def f(x, y=1, z='a'):
            pass
        f""")
        doc = defs[0].doc
        assert "f(x, y = 1, z = 'a')" in doc

    def test_class_call_signature(self):
        defs = self.goto_definitions("""
        class Foo:
            def __init__(self, x, y=1, z='a'):
                pass
        Foo""")
        doc = defs[0].doc
        assert "Foo(self, x, y = 1, z = 'a')" in doc

    def test_goto_definition_at_zero(self):
        assert self.goto_definitions("a", (1, 1)) == []
        s = self.goto_definitions("str", (1, 1))
        assert len(s) == 1
        assert list(s)[0].description == 'class str'
        assert self.goto_definitions("", (1, 0)) == []

    def test_complete_at_zero(self):
        s = self.completions("str", (1, 3))
        assert len(s) == 1
        assert list(s)[0].name == 'str'

        s = self.completions("", (1, 0))
        assert len(s) > 0

    def test_goto_definition_on_import(self):
        assert self.goto_definitions("import sys_blabla", (1, 8)) == []
        assert len(self.goto_definitions("import sys", (1, 8))) == 1

    @cwd_at('jedi')
    def test_complete_on_empty_import(self):
        # should just list the files in the directory
        assert 10 < len(self.completions("from .", path='')) < 30
        assert 10 < len(self.completions("from . import", (1, 5), '')) < 30
        assert 10 < len(self.completions("from . import classes",
                                        (1, 5), '')) < 30
        assert len(self.completions("import")) == 0
        assert len(self.completions("import import", path='')) > 0

        # 111
        assert self.completions("from datetime import")[0].name == 'import'
        assert self.completions("from datetime import ")

    @cwd_at('jedi')
    def test_add_dynamic_mods(self):
        api.settings.additional_dynamic_modules = ['dynamic.py']
        # Fictional module that defines a function.
        src1 = "def ret(a): return a"
        # Other fictional modules in another place in the fs.
        src2 = 'from .. import setup; setup.ret(1)'
        # .parser to load the module
        api.modules.Module(os.path.abspath('dynamic.py'), src2).parser
        script = jedi.Script(src1, 1, len(src1), '../setup.py')
        result = script.goto_definitions()
        assert len(result) == 1
        assert result[0].description == 'class int'

    def test_named_import(self):
        """ named import - jedi-vim issue #8 """
        s = "import time as dt"
        assert len(jedi.Script(s, 1, 15, '/').goto_definitions()) == 1
        assert len(jedi.Script(s, 1, 10, '/').goto_definitions()) == 1

    def test_unicode_script(self):
        """ normally no unicode objects are being used. (<=2.7) """
        s = unicode("import datetime; datetime.timedelta")
        completions = self.completions(s)
        assert len(completions)
        assert type(completions[0].description) is unicode

        s = utf8("author='öä'; author")
        completions = self.completions(s)
        x = completions[0].description
        assert type(x) is unicode

        s = utf8("#-*- coding: iso-8859-1 -*-\nauthor='öä'; author")
        s = s.encode('latin-1')
        completions = self.completions(s)
        assert type(completions[0].description) is unicode

    def test_multibyte_script(self):
        """ `jedi.Script` must accept multi-byte string source. """
        try:
            code = unicode("import datetime; datetime.d")
            comment = utf8("# multi-byte comment あいうえおä")
            s = (unicode('%s\n%s') % (code, comment)).encode('utf-8')
        except NameError:
            pass  # python 3 has no unicode method
        else:
            assert len(self.completions(s, (1, len(code))))

    def test_unicode_attribute(self):
        """ github jedi-vim issue #94 """
        s1 = utf8('#-*- coding: utf-8 -*-\nclass Person():\n'
                  '    name = "e"\n\nPerson().name.')
        completions1 = self.completions(s1)
        assert 'strip' in [c.name for c in completions1]
        s2 = utf8('#-*- coding: utf-8 -*-\nclass Person():\n'
                  '    name = "é"\n\nPerson().name.')
        completions2 = self.completions(s2)
        assert 'strip' in [c.name for c in completions2]

    def test_os_nowait(self):
        """ github issue #45 """
        s = self.completions("import os; os.P_")
        assert 'P_NOWAIT' in [i.name for i in s]

    def test_follow_definition(self):
        """ github issue #45 """
        c = self.completions("from datetime import timedelta; timedelta")
        # type can also point to import, but there will be additional
        # attributes
        objs = itertools.chain.from_iterable(r.follow_definition() for r in c)
        types = [o.type for o in objs]
        assert 'import' not in types and 'class' in types

    def test_keyword(self):
        """ github jedi-vim issue #44 """
        defs = self.goto_definitions("print")
        assert [d.doc for d in defs]

        defs = self.goto_definitions("import")
        assert len(defs) == 1 and [1 for d in defs if d.doc]
        # unrelated to #44
        defs = self.goto_assignments("import")
        assert len(defs) == 0
        completions = self.completions("import", (1,1))
        assert len(completions) == 0
        with common.ignored(jedi.NotFoundError):  # TODO shouldn't throw that.
            defs = self.goto_definitions("assert")
            assert len(defs) == 1

    def test_goto_assignments_keyword(self):
        """
        Bug: goto assignments on ``in`` used to raise AttributeError::

          'unicode' object has no attribute 'generate_call_path'
        """
        self.goto_assignments('in')

    def test_goto_following_on_imports(self):
        s = "import multiprocessing.dummy; multiprocessing.dummy"
        g = self.goto_assignments(s)
        assert len(g) == 1
        assert g[0].start_pos != (0, 0)

    def test_points_in_completion(self):
        """At some point, points were inserted into the completions, this
        caused problems, sometimes.
        """
        c = self.completions("if IndentationErr")
        assert c[0].name == 'IndentationError'
        self.assertEqual(c[0].complete, 'or')

    def test_docstrings_type_str(self):
        s = """
                def func(arg):
                    '''
                    :type arg: str
                    '''
                    arg."""

        names = [c.name for c in self.completions(s)]
        assert 'join' in names

    def test_docstrings_type_dotted_import(self):
        s = """
                def func(arg):
                    '''
                    :type arg: threading.Thread
                    '''
                    arg."""
        names = [c.name for c in self.completions(s)]
        assert 'start' in names

    def test_no_statement_parent(self):
        source = textwrap.dedent("""
        def f():
            pass

        class C:
            pass

        variable = f or C""")
        lines = source.splitlines()
        defs = self.goto_definitions(source, (len(lines), 3))
        defs = sorted(defs, key=lambda d: d.line)
        self.assertEqual([d.description for d in defs],
                         ['def f', 'class C'])

    def test_end_pos(self):
        # jedi issue #150
        s = "x()\nx( )\nx(  )\nx (  )"
        parser = parsing.Parser(s)
        for i, s in enumerate(parser.module.statements, 3):
            for c in s.get_commands():
                self.assertEqual(c.execution.end_pos[1], i)

    def check_definition_by_marker(self, source, after_cursor, names):
        r"""
        Find definitions specified by `after_cursor` and check what found

        For example, for the following configuration, you can pass
        ``after_cursor = 'y)'``.::

            function(
                x, y)
                   \
                    `- You want cursor to be here
        """
        source = textwrap.dedent(source)
        for (i, line) in enumerate(source.splitlines()):
            if after_cursor in line:
                break
        column = len(line) - len(after_cursor)
        defs = self.goto_definitions(source, (i + 1, column))
        self.assertEqual([d.name for d in defs], names)

    def test_backslash_continuation(self):
        """
        Test that ModuleWithCursor.get_path_until_cursor handles continuation
        """
        self.check_definition_by_marker(r"""
        x = 0
        a = \
          [1, 2, 3, 4, 5, 6, 7, 8, 9, x]  # <-- here
        """, ']  # <-- here', ['int'])

        # completion in whitespace
        s = 'asdfxyxxxxxxxx sds\\\n    hello'
        assert self.goto_assignments(s, (2, 4)) == []

    def test_backslash_continuation_and_bracket(self):
        self.check_definition_by_marker(r"""
        x = 0
        a = \
          [1, 2, 3, 4, 5, 6, 7, 8, 9, (x)]  # <-- here
        """, '(x)]  # <-- here', [None])

    def test_generator(self):
        # Did have some problems with the usage of generator completions this
        # way.
        s = "def abc():\n" \
            "    yield 1\n" \
            "abc()."
        assert self.completions(s)
