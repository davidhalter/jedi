"""
Test all things related to the ``jedi.cache`` module.
"""

import time
from os import unlink

import pytest

import jedi
from jedi import settings, cache
from jedi.parser.cache import _NodeCacheItem, save_module, load_module, \
    _get_hashed_path, parser_cache, _load_from_file_system, \
    _save_to_file_system
from jedi.parser.python import load_grammar


def test_modulepickling_change_cache_dir(monkeypatch, tmpdir):
    """
    ParserPickling should not save old cache when cache_directory is changed.

    See: `#168 <https://github.com/davidhalter/jedi/pull/168>`_
    """
    dir_1 = str(tmpdir.mkdir('first'))
    dir_2 = str(tmpdir.mkdir('second'))

    item_1 = _NodeCacheItem('bla', [])
    item_2 = _NodeCacheItem('bla', [])
    path_1 = 'fake path 1'
    path_2 = 'fake path 2'

    monkeypatch.setattr(settings, 'cache_directory', dir_1)
    grammar = load_grammar()
    _save_to_file_system(grammar, path_1, item_1)
    parser_cache.clear()
    cached = load_stored_item(grammar, path_1, item_1)
    assert cached == item_1.node

    monkeypatch.setattr(settings, 'cache_directory', dir_2)
    _save_to_file_system(grammar, path_2, item_2)
    cached = load_stored_item(grammar, path_1, item_1)
    assert cached is None


def load_stored_item(grammar, path, item):
    """Load `item` stored at `path` in `cache`."""
    item = _load_from_file_system(grammar, path, item.change_time - 1)
    return item


@pytest.mark.skip("This is currently not something we have implemented.")
@pytest.mark.usefixtures("isolated_jedi_cache")
def test_modulepickling_delete_incompatible_cache():
    item = _NodeCacheItem('fake parser', [])
    path = 'fake path'

    cache1 = ParserPicklingCls()
    cache1.version = 1
    grammar = load_grammar()
    cache1.save_item(grammar, path, item)
    cached1 = load_stored_item(grammar, cache1, path, item)
    assert cached1 == item.node

    cache2 = ParserPicklingCls()
    cache2.version = 2
    cached2 = load_stored_item(grammar, cache2, path, item)
    assert cached2 is None


@pytest.mark.usefixtures("isolated_jedi_cache")
def test_modulepickling_simulate_deleted_cache(tmpdir):
    """
    Tests loading from a cache file after it is deleted.
    According to macOS `dev docs`__,

        Note that the system may delete the Caches/ directory to free up disk
        space, so your app must be able to re-create or download these files as
        needed.

    It is possible that other supported platforms treat cache files the same
    way.

    __ https://developer.apple.com/library/content/documentation/FileManagement/Conceptual/FileSystemProgrammingGuide/FileSystemOverview/FileSystemOverview.html
    """
    grammar = load_grammar()
    module = 'fake parser'

    # Create the file
    path = tmpdir.dirname + '/some_path'
    with open(path, 'w'):
        pass

    save_module(grammar, path, module, [])
    assert load_module(grammar, path) == module

    unlink(_get_hashed_path(grammar, path))
    parser_cache.clear()

    cached2 = load_module(grammar, path)
    assert cached2 is None


@pytest.mark.skipif('True', message='Currently the star import cache is not enabled.')
def test_star_import_cache_duration():
    new = 0.01
    old, jedi.settings.star_import_cache_validity = \
        jedi.settings.star_import_cache_validity, new

    dct = cache._time_caches['star_import_cache_validity']
    old_dct = dict(dct)
    dct.clear()  # first empty...
    # path needs to be not-None (otherwise caching effects are not visible)
    jedi.Script('', 1, 0, '').completions()
    time.sleep(2 * new)
    jedi.Script('', 1, 0, '').completions()

    # reset values
    jedi.settings.star_import_cache_validity = old
    assert len(dct) == 1
    dct = old_dct
    cache._star_import_cache = {}


def test_cache_call_signatures():
    """
    See github issue #390.
    """
    def check(column, call_name, path=None):
        assert jedi.Script(s, 1, column, path).call_signatures()[0].name == call_name

    s = 'str(int())'

    for i in range(3):
        check(8, 'int')
        check(4, 'str')
        # Can keep doing these calls and always get the right result.

    # Now lets specify a source_path of boo and alternate these calls, it
    # should still work.
    for i in range(3):
        check(8, 'int', 'boo')
        check(4, 'str', 'boo')


def test_cache_line_split_issues():
    """Should still work even if there's a newline."""
    assert jedi.Script('int(\n').call_signatures()[0].name == 'int'
