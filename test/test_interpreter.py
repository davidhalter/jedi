"""
Tests of ``jedi.api.Interpreter``.
"""

from .helpers import TestCase
import jedi
from jedi._compatibility import is_py33


class TestInterpreterAPI(TestCase):
    def check_interpreter_complete(self, source, namespace, completions,
                                   **kwds):
        script = jedi.Interpreter(source, [namespace], **kwds)
        cs = script.completions()
        actual = [c.name for c in cs]
        self.assertEqual(sorted(actual), sorted(completions))

    def test_complete_raw_function(self):
        from os.path import join
        self.check_interpreter_complete('join().up',
                                        locals(),
                                        ['upper'])

    def test_complete_raw_function_different_name(self):
        from os.path import join as pjoin
        self.check_interpreter_complete('pjoin().up',
                                        locals(),
                                        ['upper'])

    def test_complete_raw_module(self):
        import os
        self.check_interpreter_complete('os.path.join().up',
                                        locals(),
                                        ['upper'])

    def test_complete_raw_instance(self):
        import datetime
        dt = datetime.datetime(2013, 1, 1)
        completions = ['time', 'timetz', 'timetuple']
        if is_py33:
            completions += ['timestamp']
        self.check_interpreter_complete('(dt - dt).ti',
                                        locals(),
                                        completions)
