"""
Tests of ``jedi.api.Interpreter``.
"""

from ..helpers import TestCase
import jedi
from jedi._compatibility import is_py33
from jedi.evaluate.compiled import mixed

class _GlobalNameSpace():
    class SideEffectContainer():
        pass


def get_completion(source, namespace):
    i = jedi.Interpreter(source, [namespace])
    completions = i.completions()
    assert len(completions) == 1
    return completions[0]


def test_builtin_details():
    import keyword

    class EmptyClass:
        pass

    variable = EmptyClass()

    def func():
        pass

    cls = get_completion('EmptyClass', locals())
    var = get_completion('variable', locals())
    f = get_completion('func', locals())
    m = get_completion('keyword', locals())
    assert cls.type == 'class'
    assert var.type == 'instance'
    assert f.type == 'function'
    assert m.type == 'module'


def test_nested_resolve():
    class XX():
        def x():
            pass

    cls = get_completion('XX', locals())
    func = get_completion('XX.x', locals())
    assert func.start_pos == (cls.start_pos[0] + 1, 12)


def test_side_effect_completion():
    """
    In the repl it's possible to cause side effects that are not documented in
    Python code, however we want references to Python code as well. Therefore
    we need some mixed kind of magic for tests.
    """
    _GlobalNameSpace.SideEffectContainer.foo = 1
    side_effect = get_completion('SideEffectContainer', _GlobalNameSpace.__dict__)

    # It's a class that contains MixedObject.
    assert isinstance(side_effect._definition.base, mixed.MixedObject)
    foo = get_completion('SideEffectContainer.foo', _GlobalNameSpace.__dict__)
    assert foo.name == 'foo'


class TestInterpreterAPI(TestCase):
    def check_interpreter_complete(self, source, namespace, completions,
                                   **kwds):
        script = jedi.Interpreter(source, [namespace], **kwds)
        cs = script.completions()
        actual = [c.name for c in cs]
        self.assertEqual(sorted(actual), sorted(completions))

    def test_complete_raw_function(self):
        from os.path import join
        self.check_interpreter_complete('join("").up',
                                        locals(),
                                        ['upper'])

    def test_complete_raw_function_different_name(self):
        from os.path import join as pjoin
        self.check_interpreter_complete('pjoin("").up',
                                        locals(),
                                        ['upper'])

    def test_complete_raw_module(self):
        import os
        self.check_interpreter_complete('os.path.join("a").up',
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

    def test_param_completion(self):
        def foo(bar):
            pass

        lambd = lambda xyz: 3

        self.check_interpreter_complete('foo(bar', locals(), ['bar'])
        # TODO we're not yet using the Python3.5 inspect.signature, yet.
        assert not jedi.Interpreter('lambd(xyz', [locals()]).completions()
