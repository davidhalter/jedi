import time
import os
import sys
import hashlib
import gc
import shutil
import pickle
import platform
import errno

from jedi import settings
from jedi import debug
from jedi._compatibility import FileNotFoundError


_PICKLE_VERSION = 30
"""
Version number (integer) for file system cache.

Increment this number when there are any incompatible changes in
the parser tree classes.  For example, the following changes
are regarded as incompatible.

- A class name is changed.
- A class is moved to another module.
- A __slot__ of a class is changed.
"""

_VERSION_TAG = '%s-%s%s-%s' % (
    platform.python_implementation(),
    sys.version_info[0],
    sys.version_info[1],
    _PICKLE_VERSION
)
"""
Short name for distinguish Python implementations and versions.

It's like `sys.implementation.cache_tag` but for Python < 3.3
we generate something similar.  See:
http://docs.python.org/3/library/sys.html#sys.implementation
"""

# for fast_parser, should not be deleted
parser_cache = {}



class _NodeCacheItem(object):
    def __init__(self, node, lines, change_time=None):
        self.node = node
        self.lines = lines
        if change_time is None:
            change_time = time.time()
        self.change_time = change_time


def load_module(grammar, path):
    """
    Returns a module or None, if it fails.
    """
    try:
        p_time = os.path.getmtime(path)
    except FileNotFoundError:
        return None

    try:
        # TODO Add grammar sha256
        module_cache_item = parser_cache[path]
        if p_time <= module_cache_item.change_time:
            return module_cache_item.node
    except KeyError:
        if not settings.use_filesystem_cache:
            return None

        return _load_from_file_system(grammar, path, p_time)


def _load_from_file_system(grammar, path, p_time):
    cache_path = _get_hashed_path(grammar, path)
    try:
        try:
            if p_time > os.path.getmtime(cache_path):
                # Cache is outdated
                return None
        except OSError as e:
            if e.errno == errno.ENOENT:
                # In Python 2 instead of an IOError here we get an OSError.
                raise FileNotFoundError
            else:
                raise

        with open(cache_path, 'rb') as f:
            gc.disable()
            try:
                module_cache_item = pickle.load(f)
            finally:
                gc.enable()
    except FileNotFoundError:
        return None
    else:
        parser_cache[path] = module_cache_item
        debug.dbg('pickle loaded: %s', path)
        return module_cache_item.node


def save_module(grammar, path, module, lines, pickling=True):
    try:
        p_time = None if path is None else os.path.getmtime(path)
    except OSError:
        p_time = None
        pickling = False

    item = _NodeCacheItem(module, lines, p_time)
    parser_cache[path] = item
    if settings.use_filesystem_cache and pickling and path is not None:
        _save_to_file_system(grammar, path, item)


def _save_to_file_system(grammar, path, item):
    with open(_get_hashed_path(grammar, path), 'wb') as f:
        pickle.dump(item, f, pickle.HIGHEST_PROTOCOL)


def remove_old_modules(self):
    """
    # TODO Might want to use such a function to clean up the cache (if it's
    # too old). We could potentially also scan for old files in the
    # directory and delete those.
    """


def clear_cache(self):
    shutil.rmtree(settings.cache_directory)
    parser_cache.clear()


def _get_hashed_path(grammar, path):
    file_hash = hashlib.sha256(path.encode("utf-8")).hexdigest()
    directory = _get_cache_directory_path()
    return os.path.join(directory, '%s-%s.pkl' % (grammar.sha256, file_hash))


def _get_cache_directory_path():
    directory = os.path.join(settings.cache_directory, _VERSION_TAG)
    if not os.path.exists(directory):
        os.makedirs(directory)
    return directory
