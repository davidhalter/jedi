"""
Test all things related to the ``jedi.cache`` module.
"""

import time

import pytest

import jedi
from jedi import settings, cache
from jedi.cache import ParserCacheItem, _ModulePickling


ModulePickling = _ModulePickling()


def test_modulepickling_change_cache_dir(monkeypatch, tmpdir):
    """
    ModulePickling should not save old cache when cache_directory is changed.

    See: `#168 <https://github.com/davidhalter/jedi/pull/168>`_
    """
    dir_1 = str(tmpdir.mkdir('first'))
    dir_2 = str(tmpdir.mkdir('second'))

    item_1 = ParserCacheItem('fake parser 1')
    item_2 = ParserCacheItem('fake parser 2')
    path_1 = 'fake path 1'
    path_2 = 'fake path 2'

    monkeypatch.setattr(settings, 'cache_directory', dir_1)
    ModulePickling.save_module(path_1, item_1)
    cached = load_stored_item(ModulePickling, path_1, item_1)
    assert cached == item_1.parser

    monkeypatch.setattr(settings, 'cache_directory', dir_2)
    ModulePickling.save_module(path_2, item_2)
    cached = load_stored_item(ModulePickling, path_1, item_1)
    assert cached is None


def load_stored_item(cache, path, item):
    """Load `item` stored at `path` in `cache`."""
    return cache.load_module(path, item.change_time - 1)


@pytest.mark.usefixtures("isolated_jedi_cache")
def test_modulepickling_delete_incompatible_cache():
    item = ParserCacheItem('fake parser')
    path = 'fake path'

    cache1 = _ModulePickling()
    cache1.version = 1
    cache1.save_module(path, item)
    cached1 = load_stored_item(cache1, path, item)
    assert cached1 == item.parser

    cache2 = _ModulePickling()
    cache2.version = 2
    cached2 = load_stored_item(cache2, path, item)
    assert cached2 is None


def test_star_import_cache_duration():
    new = 0.01
    old, jedi.settings.star_import_cache_validity = \
            jedi.settings.star_import_cache_validity, new

    cache.star_import_cache = {}  # first empty...
    # path needs to be not-None (otherwise caching effects are not visible)
    jedi.Script('', 1, 0, '').completions()
    time.sleep(2 * new)
    jedi.Script('', 1, 0, '').completions()

    # reset values
    jedi.settings.star_import_cache_validity = old
    length = len(cache.star_import_cache)
    cache.star_import_cache = {}
    assert length == 1
