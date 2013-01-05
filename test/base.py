import unittest

import sys
import os
from os.path import abspath, dirname

sys.path.insert(0, abspath(dirname(abspath(__file__)) + '/../jedi'))
os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/../jedi')

import api

#api.set_debug_function(api.debug.print_to_stdout)


class TestBase(unittest.TestCase):
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


