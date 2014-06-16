from jedi import Script


def test_function_execution():
    """
    We've been having an issue of a mutable list that was changed inside the
    function execution. Test if an execution always returns the same result.
    """

    s = """
    def x():
        return str()
    x"""
    d = Script(s).goto_definitions()[0]
    # Now just use the internals of the result (easiest way to get a fully
    # usable function).
    func, evaluator = d._definition, d._evaluator
    # Should return the same result both times.
    assert len(evaluator.execute(func)) == 1
    assert len(evaluator.execute(func)) == 1
