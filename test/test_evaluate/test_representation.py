from textwrap import dedent

from jedi import Script, names


def get_definition_and_evaluator(source):
    d = Script(dedent(source)).goto_definitions()[0]
    return d._name.parent, d._evaluator


def test_function_execution():
    """
    We've been having an issue of a mutable list that was changed inside the
    function execution. Test if an execution always returns the same result.
    """

    s = """
    def x():
        return str()
    x"""
    func, evaluator = get_definition_and_evaluator(s)
    # Now just use the internals of the result (easiest way to get a fully
    # usable function).
    # Should return the same result both times.
    assert len(evaluator.execute(func)) == 1
    assert len(evaluator.execute(func)) == 1


def test_class_mro():
    s = """
    class X(object):
        pass
    X"""
    cls, evaluator = get_definition_and_evaluator(s)
    mro = cls.py__mro__()
    assert [str(c.name) for c in mro] == ['X', 'object']


def test_instance_defined_names():
    """
    At one point, defined_names() would fail for instances
    """
    s = """
    class X(object):
        def func():
            pass
    x = X()
    """
    n = names(s)[1].defined_names()
    assert n[0].name == 'func'