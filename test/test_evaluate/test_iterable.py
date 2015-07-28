from textwrap import dedent

from jedi import names


def get_scope_and_evaluator(source):
    d = names(dedent(source))[0]
    return d.parent()._definition, d._evaluator

def find_types(s):
    scope, evaluator = get_scope_and_evaluator(s)
    return evaluator.find_types(scope, s[0])
    


def test_comprehensions():
    """
    test list/set/generator/dict comprehension syntax
    """

    s = "a = [i for i in range(10)]"
    assert len(find_types(s)) == 1
    
    s = "a = [i for i in range(10)]"
    assert len(find_types(s)) == 1
    
    s = "a = {i:i for i in range(10)}"
    assert len(find_types(s)) == 1
    
    s = "a = {i for i in range(10)}"
    assert len(find_types(s)) == 1
