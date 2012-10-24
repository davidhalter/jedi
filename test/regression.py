#!/usr/bin/env python
import os
import sys
import unittest
from os.path import abspath, dirname
import time
import functools

sys.path.append(abspath(dirname(abspath(__file__)) + '/../jedi'))
os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/../jedi')
sys.path.append('.')

from _compatibility import is_py25
import api

#api.set_debug_function(api.debug.print_to_stdout)


class Base(unittest.TestCase):
    def get_def(self, src, pos):
        script = api.Script(src, pos[0], pos[1], None)
        return script.get_definition()

    def complete(self, src, pos=None):
        if pos is None:
            pos = 1, len(src)
        script = api.Script(src, pos[0], pos[1], '')
        return script.complete()

    def get_in_function_call(self, src, pos=None):
        if pos is None:
            pos = 1, len(src)
        script = api.Script(src, pos[0], pos[1], '')
        return script.get_in_function_call()


class TestRegression(Base):
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
        assert 10 < len(self.complete("from .", (1, 5))) < 30
        assert 10 < len(self.complete("from . import", (1, 5))) < 30
        assert 10 < len(self.complete("from . import classes", (1, 5))) < 30
        assert len(self.complete("import")) == 0
        assert len(self.complete("import import")) > 0

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

        # TODO uncomment!!!! this causes some very weird errors!
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


class TestSpeed(Base):
    def _check_speed(time_per_run, number=10):
        """ Speed checks should typically be very tolerant. Some machines are
        faster than others, but the tests should still pass. These tests are
        here to assure that certain effects that kill jedi performance are not
        reintroduced to Jedi."""
        def decorated(func):
            @functools.wraps(func)
            def wrapper(self):
                first = time.time()
                for i in range(number):
                    func(self)
                single_time = (time.time() - first) / number
                print(func, single_time)
                assert single_time < time_per_run
            return wrapper
        return decorated

    # skip by removing test
    @_check_speed(0.1)
    def _test_os_path_join(self):
        s = "from posixpath import join; join('', '')."
        assert len(self.complete(s)) > 10  # is a str completion

    def test_2(self):
        # preload
        s = 'from scipy.weave import inline; inline('
        self.get_in_function_call(s)

    #@unittest.expectedFailure
    @_check_speed(0.6, number=1)
    def _test_new(self):
        s = 'import scipy.weave; scipy.weave.inline('
        api.set_debug_function(api.debug.print_to_stdout)
        #print(self.get_in_function_call(s))
        api.set_debug_function(None)
        #print(api.imports.imports_processed)


if __name__ == '__main__':
    unittest.main()
