from itertools import chain

import pytest

import jedi
from jedi._compatibility import find_module_py33
from ..helpers import cwd_at


@pytest.mark.skipif('sys.version_info < (3,3)')
def test_find_module_py33():
    """Needs to work like the old find_module."""
    assert find_module_py33('_io') == (None, '_io', False)


@cwd_at('test/test_evaluate/not_in_sys_path/pkg')
def test_import_not_in_sys_path():
    """
    non-direct imports (not in sys.path)
    """
    a = jedi.Script(path='module.py', line=5).goto_definitions()
    assert a[0].name == 'int'

    a = jedi.Script(path='module.py', line=6).goto_definitions()
    assert a[0].name == 'str'
    a = jedi.Script(path='module.py', line=7).goto_definitions()
    assert a[0].name == 'str'


def test_import_empty():
    """ github #340, return the full word. """
    completion = jedi.Script("import ").completions()[0]
    definition = completion.follow_definition()[0]
    print(definition)
    assert definition


def check_follow_definition_types(source):
    # nested import
    completions = jedi.Script(source, path='some_path.py').completions()
    defs = chain.from_iterable(c.follow_definition() for c in completions)
    return [d.type for d in defs]


def test_follow_import_incomplete():
    """
    Completion on incomplete imports should always take the full completion
    to do any evaluation.
    """
    datetime = check_follow_definition_types("import itertool")
    assert datetime == ['module']

    # empty `from * import` parts
    itert = jedi.Script("from itertools import ").completions()
    definitions = [d for d in itert if d.name == 'chain']
    assert len(definitions) == 1
    assert [d.type for d in definitions[0].follow_definition()] == ['class']

    # incomplete `from * import` part
    datetime = check_follow_definition_types("from datetime import datetim")
    assert set(datetime) == set(['class'])  # py33: builtin and pure py version

    # os.path check
    ospath = check_follow_definition_types("from os.path import abspat")
    assert ospath == ['function']

    # alias
    alias = check_follow_definition_types("import io as abcd; abcd")
    assert alias == ['module']


@cwd_at('test/completion/import_tree')
def test_follow_definition_nested_import():
    types = check_follow_definition_types("import pkg.mod1; pkg")
    assert types == ['module']

    types = check_follow_definition_types("import pkg.mod1; pkg.mod1")
    assert types == ['module']

    types = check_follow_definition_types("import pkg.mod1; pkg.mod1.a")
    assert types == ['class']


def test_follow_definition_land_on_import():
    datetime = jedi.Script("import datetime; datetim").completions()[0]
    definition = datetime.follow_definition()[0]
    print(datetime._definition, definition)
    assert definition.type == 'module'
