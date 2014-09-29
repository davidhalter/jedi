from jedi._compatibility import unicode

from jedi.evaluate import helpers
from jedi.parser import Parser


def test_statement_elements_in_statement():
    def get_stmt_els(string):
        p = Parser(unicode(string))
        return helpers.statement_elements_in_statement(p.module.statements[0])

    # list comprehension
    stmt_els = get_stmt_els('foo = [(bar(f), f) for f in baz]')
    # stmt_els: count all names: 6; + count all arrays: 2 = 8
    assert len(stmt_els) == 8

    # lambda
    stmt_els = get_stmt_els('foo = [lambda x: y]')
    # stmt_els: count all names: 3; + count all arrays: 1 = 4
    assert len(stmt_els) == 4
