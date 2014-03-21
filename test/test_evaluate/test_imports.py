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


def test_follow_import_incomplete():
    """
    Completion on incomplete imports should always take the full completion
    to do any evaluation.
    """
    datetime = jedi.Script("import datetim").completions()[0]
    definition = datetime.follow_definition()[0]
    assert definition

    # empty `from * import` parts
    datetime = jedi.Script("from datetime import ").completions()[0]
    definitions = datetime.follow_definition()
    assert [d.type for d in definitions if d.name == 'date'] == ['class']

    # incomplete `from * import` part
    datetime = jedi.Script("from datetime import datetim").completions()[0]
    definition = datetime.follow_definition()
    assert [d.type for d in definitions] == ['class']


def test_follow_definition_land_on_import():
    datetime = jedi.Script("import datetime; datetim").completions()[0]
    definition = datetime.follow_definition()[0]
    print(datetime._definition, definition)
    assert definition.type == 'module'
