#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests to avoid errors of the past. Makes use of Python's ``unittest``
module.
"""

import time
import functools
import itertools
import os
import textwrap

from .base import TestBase, unittest, cwd_at

import jedi
from jedi._compatibility import utf8, unicode
from jedi import api, parsing, common
api_classes = api.api_classes

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

    def assert_call_def(self, call_def, name, index):
        self.assertEqual(
            {'call_name': getattr(call_def, 'call_name', None),
             'index': getattr(call_def, 'index', None)},
            {'call_name': name, 'index': index},
        )

    def test_function_definition(self):
        check = self.assert_call_def

        # simple
        s = "abs(a, str("
        s2 = "abs(), "
        s3 = "abs()."
        # more complicated
        s4 = 'abs(zip(), , set,'
        s5 = "abs(1,\nif 2:\n def a():"
        s6 = "str().center("
        s7 = "str().upper().center("
        s8 = "str(int[zip("

        check(self.function_definition(s, (1, 4)), 'abs', 0)
        check(self.function_definition(s, (1, 6)), 'abs', 1)
        check(self.function_definition(s, (1, 7)), 'abs', 1)
        check(self.function_definition(s, (1, 8)), 'abs', 1)
        check(self.function_definition(s, (1, 11)), 'str', 0)

        check(self.function_definition(s2, (1, 4)), 'abs', 0)
        assert self.function_definition(s2, (1, 5)) is None
        assert self.function_definition(s2) is None

        assert self.function_definition(s3, (1, 5)) is None
        assert self.function_definition(s3) is None

        assert self.function_definition(s4, (1, 3)) is None
        check(self.function_definition(s4, (1, 4)), 'abs', 0)
        check(self.function_definition(s4, (1, 8)), 'zip', 0)
        check(self.function_definition(s4, (1, 9)), 'abs', 0)
        #check(self.function_definition(s4, (1, 10)), 'abs', 1)

        check(self.function_definition(s5, (1, 4)), 'abs', 0)
        check(self.function_definition(s5, (1, 6)), 'abs', 1)

        check(self.function_definition(s6), 'center', 0)
        check(self.function_definition(s6, (1, 4)), 'str', 0)

        check(self.function_definition(s7), 'center', 0)
        check(self.function_definition(s8), 'zip', 0)
        check(self.function_definition(s8, (1, 8)), 'str', 0)

        s = "import time; abc = time; abc.sleep("
        check(self.function_definition(s), 'sleep', 0)

        # jedi-vim #9
        s = "with open("
        check(self.function_definition(s), 'open', 0)

        # jedi-vim #11
        s1 = "for sorted("
        check(self.function_definition(s1), 'sorted', 0)
        s2 = "for s in sorted("
        check(self.function_definition(s2), 'sorted', 0)

        # jedi #57
        s = "def func(alpha, beta): pass\n" \
            "func(alpha='101',"
        check(self.function_definition(s, (2, 13)), 'func', 0)

    def test_function_definition_complex(self):
        check = self.assert_call_def

        s = """
                def abc(a,b):
                    pass

                def a(self):
                    abc(

                if 1:
                    pass
            """
        check(self.function_definition(s, (6, 24)), 'abc', 0)
        s = """
                import re
                def huhu(it):
                    re.compile(
                    return it * 2
            """
        check(self.function_definition(s, (4, 31)), 'compile', 0)
        # jedi-vim #70
        s = """def foo("""
        assert self.function_definition(s) is None
        # jedi-vim #116
        s = """import functools; test = getattr(functools, 'partial'); test("""
        check(self.function_definition(s), 'partial', 0)

    def test_function_definition_empty_paren_pre_space(self):
        s = textwrap.dedent("""\
        def f(a, b):
            pass
        f( )""")
        call_def = self.function_definition(s, (3, 3))
        self.assert_call_def(call_def, 'f', 0)

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

    def test_keyword_definition_doc(self):
        """ github jedi-vim issue #44 """
        defs = self.goto_definitions("print")
        assert [d.doc for d in defs]

        defs = self.goto_definitions("import")
        assert len(defs) == 1
        assert [d.doc for d in defs]

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
        for i, s in enumerate(parser.scope.statements, 3):
            for c in s.get_commands():
                self.assertEqual(c.execution.end_pos[1], i)


class TestDocstring(TestBase):

    def test_function_doc(self):
        defs = self.goto_definitions("""
        def func():
            '''Docstring of `func`.'''
        func""")
        self.assertEqual(defs[0].raw_doc, 'Docstring of `func`.')

    def test_attribute_docstring(self):
        defs = self.goto_definitions("""
        x = None
        '''Docstring of `x`.'''
        x""")
        self.assertEqual(defs[0].raw_doc, 'Docstring of `x`.')

    def test_multiple_docstrings(self):
        defs = self.goto_definitions("""
        def func():
            '''Original docstring.'''
        x = func
        '''Docstring of `x`.'''
        x""")
        docs = [d.raw_doc for d in defs]
        self.assertEqual(docs, ['Original docstring.', 'Docstring of `x`.'])


class TestFeature(TestBase):
    def test_full_name(self):
        """ feature request #61"""
        assert self.completions('import os; os.path.join')[0].full_name \
                                    == 'os.path.join'

    def test_keyword_full_name_should_be_none(self):
        """issue #94"""
        # Using `from jedi.keywords import Keyword` here does NOT work
        # in Python 3.  This is due to the import hack jedi using.
        Keyword = api_classes.keywords.Keyword
        d = api_classes.Definition(Keyword('(', (0, 0)))
        assert d.full_name is None

    def test_full_name_builtin(self):
        self.assertEqual(self.completions('type')[0].full_name, 'type')

    def test_full_name_tuple_mapping(self):
        s = """
        import re
        any_re = re.compile('.*')
        any_re"""
        self.assertEqual(self.goto_definitions(s)[0].full_name, 're.RegexObject')

    def test_preload_modules(self):
        def check_loaded(*modules):
            # + 1 for builtin, +1 for None module (currently used)
            assert len(new) == len(modules) + 2
            for i in modules + ('__builtin__',):
                assert [i in k for k in new.keys() if k is not None]

        from jedi import cache
        temp_cache, cache.parser_cache = cache.parser_cache, {}
        new = cache.parser_cache
        with common.ignored(KeyError): # performance of tests -> no reload
            new['__builtin__'] = temp_cache['__builtin__']

        jedi.preload_module('datetime')
        check_loaded('datetime')
        jedi.preload_module('json', 'token')
        check_loaded('datetime', 'json', 'token')

        cache.parser_cache = temp_cache

    def test_quick_completion(self):
        sources = [
            ('import json; json.l', (1, 19)),
            ('import json; json.l   ', (1, 19)),
            ('import json\njson.l', (2, 6)),
            ('import json\njson.l  ', (2, 6)),
            ('import json\njson.l\n\n', (2, 6)),
            ('import json\njson.l  \n\n', (2, 6)),
            ('import json\njson.l  \n  \n\n', (2, 6)),
        ]
        for source, pos in sources:
            # Run quick_complete
            quick_completions = api._quick_complete(source)
            # Run real completion
            script = jedi.Script(source, pos[0], pos[1], '')
            real_completions = script.completions()
            # Compare results
            quick_values = [(c.full_name, c.line, c.column) for c in quick_completions]
            real_values = [(c.full_name, c.line, c.column) for c in real_completions]
            self.assertEqual(quick_values, real_values)


class TestGetDefinitions(TestBase):

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


class TestSpeed(TestBase):
    def _check_speed(time_per_run, number=4, run_warm=True):
        """ Speed checks should typically be very tolerant. Some machines are
        faster than others, but the tests should still pass. These tests are
        here to assure that certain effects that kill jedi performance are not
        reintroduced to Jedi."""
        def decorated(func):
            @functools.wraps(func)
            def wrapper(self):
                if run_warm:
                    func(self)
                first = time.time()
                for i in range(number):
                    func(self)
                single_time = (time.time() - first) / number
                print('\nspeed', func, single_time)
                assert single_time < time_per_run
            return wrapper
        return decorated

    @_check_speed(0.2)
    def test_os_path_join(self):
        s = "from posixpath import join; join('', '')."
        assert len(self.completions(s)) > 10  # is a str completion

    @_check_speed(0.1)
    def test_scipy_speed(self):
        s = 'import scipy.weave; scipy.weave.inline('
        script = jedi.Script(s, 1, len(s), '')
        script.function_definition()
        #print(jedi.imports.imports_processed)


def test_settings_module():
    """
    jedi.settings and jedi.cache.settings must be the same module.
    """
    from jedi import cache
    from jedi import settings
    assert cache.settings is settings


def test_no_duplicate_modules():
    """
    Make sure that import hack works as expected.

    Jedi does an import hack (see: jedi/__init__.py) to have submodules
    with circular dependencies.  The modules in this circular dependency
    "loop" must be imported by ``import <module>`` rather than normal
    ``from jedi import <module>`` (or ``from . jedi ...``).  This test
    make sure that this is satisfied.

    See also:

    - `#160 <https://github.com/davidhalter/jedi/issues/160>`_
    - `#161 <https://github.com/davidhalter/jedi/issues/161>`_
    """
    import sys
    jedipath = os.path.dirname(os.path.abspath(jedi.__file__))

    def is_submodule(m):
        try:
            filepath = m.__file__
        except AttributeError:
            return False
        return os.path.abspath(filepath).startswith(jedipath)

    modules = list(filter(is_submodule, sys.modules.values()))
    top_modules = [m for m in modules if not m.__name__.startswith('jedi.')]
    for m in modules:
        if m is jedi:
            # py.test automatically improts `jedi.*` when --doctest-modules
            # is given.  So this test cannot succeeds.
            continue
        for tm in top_modules:
            try:
                imported = getattr(m, tm.__name__)
            except AttributeError:
                continue
            assert imported is tm


if __name__ == '__main__':
    unittest.main()
