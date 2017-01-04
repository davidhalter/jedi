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
    assert (func.line, func.column) == (cls.line + 1, 12)


def test_side_effect_completion():
    """
    In the repl it's possible to cause side effects that are not documented in
    Python code, however we want references to Python code as well. Therefore
    we need some mixed kind of magic for tests.
    """
    _GlobalNameSpace.SideEffectContainer.foo = 1
    side_effect = get_completion('SideEffectContainer', _GlobalNameSpace.__dict__)

    # It's a class that contains MixedObject.
    context, = side_effect._name.infer()
    assert isinstance(context, mixed.MixedObject)
    foo = get_completion('SideEffectContainer.foo', _GlobalNameSpace.__dict__)
    assert foo.name == 'foo'


def _assert_interpreter_complete(source, namespace, completions,
                                 **kwds):
    script = jedi.Interpreter(source, [namespace], **kwds)
    cs = script.completions()
    actual = [c.name for c in cs]
    assert sorted(actual) == sorted(completions)


def test_complete_raw_function():
    from os.path import join
    _assert_interpreter_complete('join("").up',
                                 locals(),
                                 ['upper'])


def test_complete_raw_function_different_name():
    from os.path import join as pjoin
    _assert_interpreter_complete('pjoin("").up',
                                 locals(),
                                 ['upper'])


def test_complete_raw_module():
    import os
    _assert_interpreter_complete('os.path.join("a").up',
                                 locals(),
                                 ['upper'])


def test_complete_raw_instance():
    import datetime
    dt = datetime.datetime(2013, 1, 1)
    completions = ['time', 'timetz', 'timetuple']
    if is_py33:
        completions += ['timestamp']
    _assert_interpreter_complete('(dt - dt).ti',
                                 locals(),
                                 completions)


def test_list():
    array = ['haha', 1]
    _assert_interpreter_complete('array[0].uppe',
                                 locals(),
                                 ['upper'])
    _assert_interpreter_complete('array[0].real',
                                 locals(),
                                 [])

    # something different, no index given, still just return the right
    _assert_interpreter_complete('array[int].real',
                                 locals(),
                                 ['real'])
    _assert_interpreter_complete('array[int()].real',
                                 locals(),
                                 ['real'])
    # inexistent index
    _assert_interpreter_complete('array[2].upper',
                                 locals(),
                                 ['upper'])


def test_slice():
    class Foo1():
        bar = []
    baz = 'xbarx'
    _assert_interpreter_complete('getattr(Foo1, baz[1:-1]).append',
                                 locals(),
                                 ['append'])


def test_getitem_side_effects():
    class Foo2():
        def __getitem__(self, index):
            # possible side effects here, should therefore not call this.
            return index

    foo = Foo2()
    _assert_interpreter_complete('foo[0].', locals(), [])


def test_property_error():
    class Foo3():
        @property
        def bar(self):
            raise ValueError

    foo = Foo3()
    _assert_interpreter_complete('foo.bar', locals(), ['bar'])
    _assert_interpreter_complete('foo.bar.baz', locals(), [])


def test_param_completion():
    def foo(bar):
        pass

    lambd = lambda xyz: 3

    _assert_interpreter_complete('foo(bar', locals(), ['bar'])
    # TODO we're not yet using the Python3.5 inspect.signature, yet.
    assert not jedi.Interpreter('lambd(xyz', [locals()]).completions()
