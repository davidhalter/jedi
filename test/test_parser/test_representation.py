from jedi.parser import Parser
from jedi.parser import representation as pr
from jedi._compatibility import u


def test_import_is_nested():
    imp = Parser(u('import ')).module.imports[0]
    # should not raise an error, even if it's not a complete import
    assert not imp.is_nested()


def test_module_scope_name_generator():
    assert pr.Module().scope_names_generator()
