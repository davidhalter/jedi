import inspect
import time
import os
import sys
import json
import hashlib
import gc
import shutil
import pickle

from jedi import settings
from jedi import debug
from jedi._compatibility import FileNotFoundError


def underscore_memoization(func):
    """
    Decorator for methods::

        class A(object):
            def x(self):
                if self._x:
                    self._x = 10
                return self._x

    Becomes::

        class A(object):
            @underscore_memoization
            def x(self):
                return 10

    A now has an attribute ``_x`` written by this decorator.
    """
    name = '_' + func.__name__

    def wrapper(self):
        try:
            return getattr(self, name)
        except AttributeError:
            result = func(self)
            if inspect.isgenerator(result):
                result = list(result)
            setattr(self, name, result)
            return result

    return wrapper


# for fast_parser, should not be deleted
parser_cache = {}


class ParserCacheItem(object):
    def __init__(self, parser, change_time=None):
        self.parser = parser
        if change_time is None:
            change_time = time.time()
        self.change_time = change_time


def load_parser(grammar, path):
    """
    Returns the module or None, if it fails.
    """
    p_time = os.path.getmtime(path) if path else None
    try:
        parser_cache_item = parser_cache[path]
        if not path or p_time <= parser_cache_item.change_time:
            return parser_cache_item.parser
    except KeyError:
        if settings.use_filesystem_cache:
            return ParserPickling.load_parser(grammar, path, p_time)


def save_parser(grammar, path, parser, pickling=True):
    try:
        p_time = None if path is None else os.path.getmtime(path)
    except OSError:
        p_time = None
        pickling = False

    item = ParserCacheItem(parser, p_time)
    parser_cache[path] = item
    if settings.use_filesystem_cache and pickling:
        ParserPickling.save_parser(grammar, path, item)


class ParserPickling(object):
    version = 28
    """
    Version number (integer) for file system cache.

    Increment this number when there are any incompatible changes in
    parser representation classes.  For example, the following changes
    are regarded as incompatible.

    - Class name is changed.
    - Class is moved to another module.
    - Defined slot of the class is changed.
    """

    def __init__(self):
        self.__index = None
        self.py_tag = 'cpython-%s%s' % sys.version_info[:2]
        """
        Short name for distinguish Python implementations and versions.

        It's like `sys.implementation.cache_tag` but for Python < 3.3
        we generate something similar.  See:
        http://docs.python.org/3/library/sys.html#sys.implementation

        .. todo:: Detect interpreter (e.g., PyPy).
        """

    def load_parser(self, grammar, path, original_changed_time):
        """
        Try to load the parser for `path`, unless `original_changed_time` is
        greater than the original pickling time. In which case the pickled
        parser is not up to date.
        """
        try:
            pickle_changed_time = self._index[path]
        except KeyError:
            return None
        if original_changed_time is not None \
                and pickle_changed_time < original_changed_time:
            # the pickle file is outdated
            return None

        try:
            with open(self._get_hashed_path(grammar, path), 'rb') as f:
                try:
                    gc.disable()
                    parser_cache_item = pickle.load(f)
                finally:
                    gc.enable()
        except FileNotFoundError:
            return None

        debug.dbg('pickle loaded: %s', path)
        parser_cache[path] = parser_cache_item
        return parser_cache_item.parser

    def save_parser(self, grammar, path, parser_cache_item):
        self.__index = None
        try:
            files = self._index
        except KeyError:
            files = {}
            self._index = files

        with open(self._get_hashed_path(grammar, path), 'wb') as f:
            pickle.dump(parser_cache_item, f, pickle.HIGHEST_PROTOCOL)
            files[path] = parser_cache_item.change_time

        self._flush_index()

    @property
    def _index(self):
        if self.__index is None:
            try:
                with open(self._get_path('index.json')) as f:
                    data = json.load(f)
            except (IOError, ValueError):
                self.__index = {}
            else:
                # 0 means version is not defined (= always delete cache):
                if data.get('version', 0) != self.version:
                    self.clear_cache()
                else:
                    self.__index = data['index']
        return self.__index

    def _remove_old_modules(self):
        # TODO use
        change = False
        if change:
            self._flush_index(self)
            self._index  # reload index

    def _flush_index(self):
        data = {'version': self.version, 'index': self._index}
        with open(self._get_path('index.json'), 'w') as f:
            json.dump(data, f)
        self.__index = None

    def clear_cache(self):
        shutil.rmtree(self._cache_directory())
        self.__index = {}

    def _get_hashed_path(self, grammar, path):
        file_hash = hashlib.sha256(path.encode("utf-8")).hexdigest()
        return self._get_path('%s-%s.pkl' % (grammar.sha256, file_hash))

    def _get_path(self, file):
        dir = self._cache_directory()
        if not os.path.exists(dir):
            os.makedirs(dir)
        return os.path.join(dir, file)

    def _cache_directory(self):
        return os.path.join(settings.cache_directory, self.py_tag)


# is a singleton
ParserPickling = ParserPickling()
