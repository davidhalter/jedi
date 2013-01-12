from __future__ import with_statement

import time
import os
import sys
import pickle

from _compatibility import json
import settings
import debug

# memoize caches will be deleted after every action
memoize_caches = []

time_caches = []

star_import_cache = {}

# for fast_parser, should not be deleted
parser_cache = {}


class ParserCacheItem(object):
    def __init__(self, parser, change_time=None):
        self.parser = parser
        if change_time is None:
            change_time = time.time()
        self.change_time = change_time


def clear_caches(delete_all=False):
    """ Jedi caches many things, that should be completed after each completion
    finishes.

    :param delete_all: Deletes also the cache that is normally not deleted,
        like parser cache, which is important for faster parsing.
    """
    global memoize_caches, time_caches

    # memorize_caches must never be deleted, because the dicts will get lost in
    # the wrappers.
    for m in memoize_caches:
        m.clear()

    if delete_all:
        time_caches = []
        star_import_cache.clear()
        parser_cache.clear()
    else:
        # normally just kill the expired entries, not all
        for tc in time_caches:
            # check time_cache for expired entries
            for key, (t, value) in list(tc.items()):
                if t < time.time():
                    # delete expired entries
                    del tc[key]


def memoize_default(default=None, cache=memoize_caches):
    """ This is a typical memoization decorator, BUT there is one difference:
    To prevent recursion it sets defaults.

    Preventing recursion is in this case the much bigger use than speed. I
    don't think, that there is a big speed difference, but there are many cases
    where recursion could happen (think about a = b; b = a).
    """
    def func(function):
        memo = {}
        cache.append(memo)

        def wrapper(*args, **kwargs):
            key = (args, frozenset(kwargs.items()))
            if key in memo:
                return memo[key]
            else:
                memo[key] = default
                rv = function(*args, **kwargs)
                memo[key] = rv
                return rv
        return wrapper
    return func


class CachedMetaClass(type):
    """ This is basically almost the same than the decorator above, it just
    caches class initializations. I haven't found any other way, so I do it
    with meta classes.
    """
    @memoize_default()
    def __call__(self, *args, **kwargs):
        return super(CachedMetaClass, self).__call__(*args, **kwargs)


def time_cache(time_add_setting):
    """ This decorator works as follows: Call it with a setting and after that
    use the function with a callable that returns the key.
    But: This function is only called if the key is not available. After a
    certain amount of time (`time_add_setting`) the cache is invalid.
    """
    def _temp(key_func):
        dct = {}
        time_caches.append(dct)

        def wrapper(optional_callable, *args, **kwargs):
            key = key_func(*args, **kwargs)
            value = None
            if key in dct:
                expiry, value = dct[key]
                if expiry > time.time():
                    return value
            value = optional_callable()
            time_add = getattr(settings, time_add_setting)
            if key is not None:
                dct[key] = time.time() + time_add, value
            return value
        return wrapper
    return _temp


@time_cache("get_in_function_call_validity")
def cache_get_in_function_call(stmt):
    module_path = stmt.get_parent_until().path
    return None if module_path is None else (module_path, stmt.start_pos)


def cache_star_import(func):
    def wrapper(scope, *args, **kwargs):
        try:
            mods = star_import_cache[scope]
            if mods[0] + settings.star_import_cache_validity > time.time():
                return mods[1]
        except KeyError:
            pass
        # cache is too old and therefore invalid or not available
        invalidate_star_import_cache(scope)
        mods = func(scope, *args, **kwargs)
        star_import_cache[scope] = time.time(), mods

        return mods
    return wrapper


def invalidate_star_import_cache(module, only_main=False):
    """ Important if some new modules are being reparsed """
    try:
        t, mods = star_import_cache[module]

        del star_import_cache[module]

        for m in mods:
            invalidate_star_import_cache(m, only_main=True)
    except KeyError:
        pass

    if not only_main:
        # We need a list here because otherwise the list is being changed
        # during the iteration in py3k: iteritems -> items.
        for key, (t, mods) in list(star_import_cache.items()):
            if module in mods:
                invalidate_star_import_cache(key)


def load_module(path, name):
    """
    Returns the module or None, if it fails.
    """
    if path is None and name is None:
        return None

    tim = os.path.getmtime(path) if path else None
    n = name if path is None else path
    try:
        parser_cache_item = parser_cache[n]
        if not path or tim <= parser_cache_item.change_time:
            return parser_cache_item.parser
        else:
            # In case there is already a module cached and this module
            # has to be reparsed, we also need to invalidate the import
            # caches.
            invalidate_star_import_cache(parser_cache_item.parser.module)
    except KeyError:
        if settings.use_filesystem_cache:
            return ModulePickling.load_module(n, tim)


def save_module(path, name, parser, pickling=True):
    try:
        p_time = None if not path else os.path.getmtime(path)
    except OSError:
        p_time = None
        pickling = False

    n = name if path is None else path
    item = ParserCacheItem(parser, p_time)
    parser_cache[n] = item
    if settings.use_filesystem_cache and pickling:
        ModulePickling.save_module(n, item)


class _ModulePickling(object):
    def __init__(self):
        self.__index = None
        self.py_version = '%s.%s' % sys.version_info[:2]

    def load_module(self, path, original_changed_time):
        try:
            pickle_changed_time = self._index[self.py_version][path]
        except KeyError:
            return None
        if original_changed_time is not None \
                and pickle_changed_time < original_changed_time:
            # the pickle file is outdated
            return None

        with open(self._get_hashed_path(path), 'rb') as f:
            parser_cache_item = pickle.load(f)

        debug.dbg('pickle loaded', path)
        parser_cache[path] = parser_cache_item
        return parser_cache_item.parser

    def save_module(self, path, parser_cache_item):
        try:
            files = self._index[self.py_version]
        except KeyError:
            files = {}
            self._index[self.py_version] = files

        with open(self._get_hashed_path(path), 'wb') as f:
            pickle.dump(parser_cache_item, f, pickle.HIGHEST_PROTOCOL)
            files[path] = parser_cache_item.change_time

        self._flush_index()

    @property
    def _index(self):
        if self.__index is None:
            try:
                with open(self._get_path('index.json')) as f:
                    self.__index = json.load(f)
            except IOError:
                self.__index = {}
        return self.__index

    def _remove_old_modules(self):
        # TODO use
        change = False
        if change:
            self._flush_index(self)
            self._index  # reload index

    def _flush_index(self):
        with open(self._get_path('index.json'), 'w') as f:
            json.dump(self._index, f)
        self.__index = None

    def _get_hashed_path(self, path):
        return self._get_path('%s_%s.pkl' % (self.py_version, hash(path)))

    def _get_path(self, file):
        dir = settings.cache_directory
        if not os.path.exists(dir):
            os.makedirs(dir)
        return dir + os.path.sep + file


# is a singleton
ModulePickling = _ModulePickling()
