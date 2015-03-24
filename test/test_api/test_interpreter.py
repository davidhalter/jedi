"""
Tests of ``jedi.api.Interpreter``.
"""

from ..helpers import TestCase
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

    def test_list(self):
        array = ['haha', 1]
        self.check_interpreter_complete('array[0].uppe',
                                        locals(),
                                        ['upper'])
        self.check_interpreter_complete('array[0].real',
                                        locals(),
                                        [])

        # something different, no index given, still just return the right
        self.check_interpreter_complete('array[int].real',
                                        locals(),
                                        ['real'])
        self.check_interpreter_complete('array[int()].real',
                                        locals(),
                                        ['real'])
        # inexistent index
        self.check_interpreter_complete('array[2].upper',
                                        locals(),
                                        ['upper'])

    def test_slice(self):
        class Foo():
            bar = []
        baz = 'xbarx'
        self.check_interpreter_complete('getattr(Foo, baz[1:-1]).append',
                                        locals(),
                                        ['append'])

    def test_getitem_side_effects(self):
        class Foo():
            def __getitem__(self, index):
                # possible side effects here, should therefore not call this.
                return index

        foo = Foo()
        self.check_interpreter_complete('foo[0].', locals(), [])

    def test_property_error(self):
        class Foo():
            @property
            def bar(self):
                raise ValueError

        foo = Foo()
        self.check_interpreter_complete('foo.bar', locals(), ['bar'])
        self.check_interpreter_complete('foo.bar.baz', locals(), [])
