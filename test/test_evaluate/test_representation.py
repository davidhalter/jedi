from textwrap import dedent


def get_definition_and_evaluator(Script, source):
    first, = Script(dedent(source)).goto_definitions()
    return first._name._context, first._evaluator


def test_function_execution(Script):
    """
    We've been having an issue of a mutable list that was changed inside the
    function execution. Test if an execution always returns the same result.
    """

    s = """
    def x():
        return str()
    x"""
    func, evaluator = get_definition_and_evaluator(Script, s)
    # Now just use the internals of the result (easiest way to get a fully
    # usable function).
    # Should return the same result both times.
    assert len(func.execute_evaluated()) == 1
    assert len(func.execute_evaluated()) == 1


def test_class_mro(Script):
    s = """
    class X(object):
        pass
    X"""
    cls, evaluator = get_definition_and_evaluator(Script, s)
    mro = cls.py__mro__()
    assert [c.name.string_name for c in mro] == ['X', 'object']
