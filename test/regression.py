#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import unittest
from os.path import abspath, dirname
import time
import functools
import itertools

sys.path.insert(0, abspath(dirname(abspath(__file__)) + '/../jedi'))
os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/../jedi')

from _compatibility import is_py25, utf8, unicode
import api

#api.set_debug_function(api.debug.print_to_stdout)


class Base(unittest.TestCase):
    def get_script(self, src, pos, path=None):
        if pos is None:
            lines = src.splitlines()
            pos = len(lines), len(lines[-1])
        return api.Script(src, pos[0], pos[1], path)

    def get_def(self, src, pos=None):
        script = self.get_script(src, pos)
        return script.get_definition()

    def complete(self, src, pos=None, path=None):
        script = self.get_script(src, pos, path)
        return script.complete()

    def goto(self, src, pos=None):
        script = self.get_script(src, pos)
        return script.goto()

    def get_in_function_call(self, src, pos=None):
        script = self.get_script(src, pos)
        return script.get_in_function_call()


class TestRegression(Base):
    def test_star_import_cache_duration(self):
        new = 0.01
        old, api.settings.star_import_cache_validity = \
                api.settings.star_import_cache_validity, new

        cache = api.cache
        cache.star_import_cache = {}  # first empty...
        # path needs to be not-None (otherwise caching effects are not visible)
        api.Script('', 1, 0, '').complete()
        time.sleep(2 * new)
        api.Script('', 1, 0, '').complete()

        # reset values
        api.settings.star_import_cache_validity = old
        length = len(cache.star_import_cache)
        cache.star_import_cache = {}
        self.assertEqual(length, 1)

    def test_part_parser(self):
        """ test the get_in_function_call speedups """
        s = '\n' * 100 + 'abs('
        pos = 101, 4
        self.get_in_function_call(s, pos)
        assert self.get_in_function_call(s, pos)

    def test_get_definition_cursor(self):

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

        get_def = lambda pos: [d.description for d in self.get_def(s, pos)]
        in_name = get_def(in_name)
        under_score = get_def(under_score)
        should1 = get_def(should1)
        should2 = get_def(should2)

        diff_line = get_def(diff_line)

        assert should1 == in_name
        assert should1 == under_score

        #print should2, diff_line
        assert should2 == diff_line

        self.assertRaises(api.NotFoundError, get_def, cls)

    def test_keyword_doc(self):
        r = list(self.get_def("or", (1, 1)))
        assert len(r) == 1
        if not is_py25:
            assert len(r[0].doc) > 100

        r = list(self.get_def("asfdasfd", (1, 1)))
        assert len(r) == 0

    def test_operator_doc(self):
        r = list(self.get_def("a == b", (1, 3)))
        assert len(r) == 1
        if not is_py25:
            assert len(r[0].doc) > 100

    def test_get_definition_at_zero(self):
        assert self.get_def("a", (1, 1)) == []
        s = self.get_def("str", (1, 1))
        assert len(s) == 1
        assert list(s)[0].description == 'class str'
        assert self.get_def("", (1, 0)) == []

    def test_complete_at_zero(self):
        s = self.complete("str", (1, 3))
        assert len(s) == 1
        assert list(s)[0].word == 'str'

        s = self.complete("", (1, 0))
        assert len(s) > 0

    def test_get_definition_on_import(self):
        assert self.get_def("import sys_blabla", (1, 8)) == []
        assert len(self.get_def("import sys", (1, 8))) == 1

    def test_complete_on_empty_import(self):
        # should just list the files in the directory
        assert 10 < len(self.complete("from .", path='')) < 30
        assert 10 < len(self.complete("from . import", (1, 5), '')) < 30
        assert 10 < len(self.complete("from . import classes",
                                        (1, 5), '')) < 30
        assert len(self.complete("import")) == 0
        assert len(self.complete("import import", path='')) > 0

    def test_get_in_function_call(self):
        def check(call_def, name, index):
            return call_def and call_def.call_name == name \
                            and call_def.index == index

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

        assert check(self.get_in_function_call(s, (1, 4)), 'abs', 0)
        assert check(self.get_in_function_call(s, (1, 6)), 'abs', 1)
        assert check(self.get_in_function_call(s, (1, 7)), 'abs', 1)
        assert check(self.get_in_function_call(s, (1, 8)), 'abs', 1)
        assert check(self.get_in_function_call(s, (1, 11)), 'str', 0)

        assert check(self.get_in_function_call(s2, (1, 4)), 'abs', 0)
        assert self.get_in_function_call(s2, (1, 5)) is None
        assert self.get_in_function_call(s2) is None

        assert self.get_in_function_call(s3, (1, 5)) is None
        assert self.get_in_function_call(s3) is None

        assert self.get_in_function_call(s4, (1, 3)) is None
        assert check(self.get_in_function_call(s4, (1, 4)), 'abs', 0)
        assert check(self.get_in_function_call(s4, (1, 8)), 'zip', 0)
        assert check(self.get_in_function_call(s4, (1, 9)), 'abs', 0)
        assert check(self.get_in_function_call(s4, (1, 10)), 'abs', 1)

        assert check(self.get_in_function_call(s5, (1, 4)), 'abs', 0)
        assert check(self.get_in_function_call(s5, (1, 6)), 'abs', 1)

        assert check(self.get_in_function_call(s6), 'center', 0)
        assert check(self.get_in_function_call(s6, (1, 4)), 'str', 0)

        assert check(self.get_in_function_call(s7), 'center', 0)
        assert check(self.get_in_function_call(s8), 'zip', 0)
        assert check(self.get_in_function_call(s8, (1, 8)), 'str', 0)

        s = "import time; abc = time; abc.sleep("
        assert check(self.get_in_function_call(s), 'sleep', 0)

        # jedi-vim #9
        s = "with open("
        assert check(self.get_in_function_call(s), 'open', 0)

        # jedi-vim #11
        s1 = "for sorted("
        assert check(self.get_in_function_call(s1), 'sorted', 0)
        s2 = "for s in sorted("
        assert check(self.get_in_function_call(s2), 'sorted', 0)

        # jedi #57
        s = "def func(alpha, beta): pass\n" \
            "func(alpha='101',"
        assert check(self.get_in_function_call(s, (2, 13)), 'func', 0)

    def test_get_in_function_call_complex(self):
        def check(call_def, name, index):
            return call_def and call_def.call_name == name \
                            and call_def.index == index

        s = """
                def abc(a,b):
                    pass

                def a(self):
                    abc(

                if 1:
                    pass
            """
        assert check(self.get_in_function_call(s, (6, 24)), 'abc', 0)
        s = """
                import re
                def huhu(it):
                    re.compile(
                    return it * 2
            """
        assert check(self.get_in_function_call(s, (4, 31)), 'compile', 0)

    def test_add_dynamic_mods(self):
        api.settings.additional_dynamic_modules = ['dynamic.py']
        # Fictional module that defines a function.
        src1 = "def ret(a): return a"
        # Other fictional modules in another place in the fs.
        src2 = 'from .. import setup; setup.ret(1)'
        # .parser to load the module
        api.modules.Module(os.path.abspath('dynamic.py'), src2).parser
        script = api.Script(src1, 1, len(src1), '../setup.py')
        result = script.get_definition()
        assert len(result) == 1
        assert result[0].description == 'class int'

    def test_named_import(self):
        """ named import - jedi-vim issue #8 """
        s = "import time as dt"
        assert len(api.Script(s, 1, 15, '/').get_definition()) == 1
        assert len(api.Script(s, 1, 10, '/').get_definition()) == 1

    def test_unicode_script(self):
        """ normally no unicode objects are being used. (<=2.7) """
        s = unicode("import datetime; datetime.timedelta")
        completions = self.complete(s)
        assert len(completions)
        assert type(completions[0].description) is unicode

        s = utf8("author='öä'; author")
        completions = self.complete(s)
        assert type(completions[0].description) is unicode

        s = utf8("#-*- coding: iso-8859-1 -*-\nauthor='öä'; author")
        s = s.encode('latin-1')
        completions = self.complete(s)
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
            assert len(self.complete(s, (1, len(code))))

    def test_os_nowait(self):
        """ github issue #45 """
        s = self.complete("import os; os.P_")
        assert 'P_NOWAIT' in [i.word for i in s]

    def test_follow_definition(self):
        """ github issue #45 """
        c = self.complete("from datetime import timedelta; timedelta")
        # type can also point to import, but there will be additional
        # attributes
        objs = itertools.chain.from_iterable(r.follow_definition() for r in c)
        types = [o.type for o in objs]
        assert 'Import' not in types and 'Class' in types

    def test_keyword_definition_doc(self):
        """ github jedi-vim issue #44 """
        defs = self.get_def("print")
        assert [d.doc for d in defs]

        defs = self.get_def("import")
        assert len(defs) == 1
        assert [d.doc for d in defs]

    def test_goto_following_on_imports(self):
        if is_py25:
            return
        g = self.goto("import multiprocessing.dummy; multiprocessing.dummy")
        assert len(g) == 1
        assert g[0].start_pos != (0, 0)

    def test_points_in_completion(self):
        """At some point, points were inserted into the completions, this
        caused problems, sometimes.
        """
        c = self.complete("if IndentationErr")
        assert c[0].word == 'IndentationError'
        self.assertEqual(c[0].complete, 'or')


class TestFeature(Base):
    def test_full_name(self):
        """ feature request #61"""
        assert self.complete('import os; os.path.join')[0].full_name \
                                    == 'os.path.join'
        # issue #94
        defs = self.get_def("""import json; json.load(""")
        assert defs[0].full_name is None

    def test_full_name_builtin(self):
        self.assertEqual(self.complete('type')[0].full_name, 'type')

    def test_full_name_tuple_mapping(self):
        s = """
        import re
        any_re = re.compile('.*')
        any_re"""
        self.assertEqual(self.get_def(s)[0].full_name, 're.RegexObject')


class TestSpeed(Base):
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

    @_check_speed(0.1)
    def test_os_path_join(self):
        s = "from posixpath import join; join('', '')."
        assert len(self.complete(s)) > 10  # is a str completion

    @_check_speed(0.1)
    def test_scipy_speed(self):
        s = 'import scipy.weave; scipy.weave.inline('
        script = api.Script(s, 1, len(s), '')
        script.get_in_function_call()
        #print(api.imports.imports_processed)

if __name__ == '__main__':
    unittest.main()
