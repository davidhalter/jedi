from jedi.evaluate.helpers import deep_ast_copy
from jedi.parser import representation as pr


def test_deep_ast_copy():
    name = pr.Name(object, [('hallo', (0, 0))], (0, 0), (0, 0))

    # fast parent copy should switch parent
    new_name = deep_ast_copy(name)
    assert new_name.names[0].parent == new_name
