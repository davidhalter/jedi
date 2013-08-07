#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests to avoid errors of the past. Makes use of Python's ``unittest``
module.
"""

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

    def test_os_nowait(self):
        """ github issue #45 """
        s = self.completions("import os; os.P_")
        assert 'P_NOWAIT' in [i.name for i in s]

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

    def test_points_in_completion(self):
        """At some point, points were inserted into the completions, this
        caused problems, sometimes.
        """
        c = self.completions("if IndentationErr")
        assert c[0].name == 'IndentationError'
        self.assertEqual(c[0].complete, 'or')

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
