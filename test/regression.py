#!/usr/bin/env python
import os
import sys
import unittest
from os.path import abspath, dirname

sys.path.append(abspath(dirname(abspath(__file__)) + '/..'))
os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
sys.path.append('.')

from _compatibility import is_py25
import api
#api.set_debug_function(api.debug.print_to_stdout)


class TestRegression(unittest.TestCase):
    def get_def(self, src, pos):
        script = api.Script(src, pos[0], pos[1], '')
        return script.get_definition()

    def complete(self, src, pos):
        script = api.Script(src, pos[0], pos[1], '')
        return script.complete()

    def get_in_function_call(self, src, pos=None):
        if pos is None:
            pos = 1, len(src)
        script = api.Script(src, pos[0], pos[1], '')
        return script.get_in_function_call()

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

        s = self.complete("", (1,0))
        assert len(s) > 0

    def test_get_definition_on_import(self):
        assert self.get_def("import sys_blabla", (1, 8)) == []
        assert len(self.get_def("import sys", (1, 8))) == 1

    def test_complete_on_empty_import(self):
        # should just list the files in the directory
        assert 10 < len(self.complete("from .", (1, 5))) < 30
        assert 10 < len(self.complete("from . import", (1, 5))) < 30
        assert 10 < len(self.complete("from . import classes", (1, 5))) < 30

    def test_new(self):
        """ This is just to try out things, removing or deleting it is ok. """
        s = ("def abc(): pass\n"
             "abc.d.a.abc.d"
             )
        api.Script(s, 2, 2, '/').related_names()

    def test_get_in_function_call(self):
        s = "isinstance(a, abs("
        s2 = "isinstance(), "

        check = lambda call_def, index: call_def and call_def.index == index
        assert check(self.get_in_function_call(s, (1,11)), 0)
        assert check(self.get_in_function_call(s, (1,14)), 1)
        assert check(self.get_in_function_call(s, (1,15)), 1)
        assert check(self.get_in_function_call(s, (1,18)), 0)

        #assert check(self.get_in_function_call(s2, (1,11)), 0) # TODO uncomment
        assert self.get_in_function_call(s2, (1,12)) is None
        assert self.get_in_function_call(s2) is None

if __name__ == '__main__':
    unittest.main()
