from jedi._compatibility import unicode
from jedi.parser import Parser, load_grammar
from jedi.evaluate import sys_path, Evaluator


def test_paths_from_assignment():
    def paths(src):
        grammar = load_grammar()
        stmt = Parser(grammar, unicode(src)).module.statements[0]
        return list(sys_path._paths_from_assignment(Evaluator(grammar), stmt))

    assert paths('sys.path[0:0] = ["a"]') == ['a']
    assert paths('sys.path = ["b", 1, x + 3, y, "c"]') == ['b', 'c']
    assert paths('sys.path = a = ["a"]') == ['a']

    # Fail for complicated examples.
    assert paths('sys.path, other = ["a"], 2') == []
