from jedi.evaluate import helpers
from jedi.parser import representation as pr
from jedi.parser import Parser


def test_deep_ast_copy():
    name = pr.Name(object, [('hallo', (0, 0))], (0, 0), (0, 0))

    # fast parent copy should switch parent
    new_name = helpers.deep_ast_copy(name)
    assert new_name.names[0].parent == new_name


def test_statement_elements_in_statement():
    def get_stmt_els(string):
        p = Parser(string)
        return helpers.statement_elements_in_statement(p.module.statements[0])

    stmt_els = get_stmt_els('foo = [(bar(f), f) for f in baz]')
    # stmt_els: count all names: 6; + count all arrays: 2 = 8
    assert len(stmt_els) == 8
