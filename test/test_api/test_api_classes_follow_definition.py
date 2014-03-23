from itertools import chain

import jedi
from ..helpers import cwd_at


def test_import_empty():
    """ github #340, return the full word. """
    completion = jedi.Script("import ").completions()[0]
    definition = completion.follow_definition()[0]
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
    types = check_follow_definition_types("import datetime; datetim")
    assert types == ['module']
