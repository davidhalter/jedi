"""
Imitate the parser representation.
"""
import inspect
import re
import sys
import os

from jedi._compatibility import builtins as _builtins, is_py3k, exec_function
from jedi import debug
from jedi.parser.representation import Base
from jedi.cache import underscore_memoization
from jedi.evaluate.sys_path import get_sys_path


# TODO
# unbound methods such as pyqtSignals have no __name__
# if not hasattr(func, "__name__"):

class PyObject(Base):
    def __init__(self, obj, parent=None, instantiated=False):
        self.obj = obj
        self.parent = parent
        self.instantiated = instantiated
        self.doc = inspect.getdoc(obj)

        # comply with the parser
        self.get_parent_until = lambda *args, **kwargs: parent or self
        self.start_pos = 0, 0

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.obj)

    @underscore_memoization
    def _parse_function_doc(self):
        if self.doc is None:
            return '', ''

        return _parse_function_doc(self.doc)

    def type(self):
        cls = self._cls().obj
        if inspect.isclass(cls):
            return 'class'
        elif inspect.ismodule(cls):
            return 'module'
        elif inspect.isbuiltin(cls) or inspect.ismethod(cls) \
                or inspect.ismethoddescriptor(cls):
            return 'def'

    @underscore_memoization
    def _cls(self):
        # Ensures that a PyObject is returned that is not an instance (like list)
        if not (inspect.isclass(self.obj) or inspect.ismodule(self.obj)
                or inspect.isbuiltin(self.obj) or inspect.ismethod(self.obj)
                or inspect.ismethoddescriptor(self.obj)):
            return PyObject(self.obj.__class__, self.parent, True)
        return self

    def get_defined_names(self):
        cls = self._cls()
        for name in dir(cls.obj):
            yield PyName(cls, name)

    @property
    def name(self):
        # might not exist sometimes (raises AttributeError)
        return self._cls().obj.__name__

    def execute(self, params):
        t = self.type()
        if t == 'class':
            if not self.instantiated:
                yield PyObject(self.obj, self.parent, True)
        elif t == 'def':
            for name in self._parse_function_doc()[1].split():
                try:
                    yield PyObject(getattr(_builtins, name), builtin, True)
                except AttributeError:
                    pass

    def get_self_attributes(self):
        return []  # Instance compatibility

    def get_imports(self):
        return []  # Builtins don't have imports


class PyName(object):
    def __init__(self, obj, name):
        self._obj = obj
        self._name = name
        self.start_pos = 0, 0  # an illegal start_pos, to make sorting easy.

    def __repr__(self):
        return '<%s: (%s).%s>' % (type(self).__name__, repr(self._obj.obj), self._name)

    @property
    @underscore_memoization
    def parent(self):
        try:
            # this has a builtin_function_or_method
            return PyObject(getattr(self._obj.obj, self._name), self._obj)
        except AttributeError:
            # happens e.g. in properties of
            # PyQt4.QtGui.QStyleOptionComboBox.currentText
            # -> just set it to None
            return PyObject(None, builtin)

    @property
    def names(self):
        return [self._name]  # compatibility with parser.representation.Name

    def get_code(self):
        return self._name

import os.path as osp
import imp
def get_parent_until(path):
    """
    Given a file path, determine the full module path

    e.g. '/usr/lib/python2.7/dist-packages/numpy/core/__init__.pyc' yields
    'numpy.core'
    """
    dirname = osp.dirname(path)
    try:
        mod = osp.basename(path)
        mod = osp.splitext(mod)[0]
        imp.find_module(mod, [dirname])
    except ImportError:
        return
    items = [mod]
    while 1:
        items.append(osp.basename(dirname))
        try:
            dirname = osp.dirname(dirname)
            imp.find_module('__init__', [dirname + os.sep])
        except ImportError:
            break
    return '.'.join(reversed(items))


def load_module(path, name):
    if not name:
        name = os.path.basename(path)
        name = name.rpartition('.')[0]  # cut file type (normally .so)

    sys_path = get_sys_path()
    if path:
        sys_path.insert(0, path)

    temp, sys.path = sys.path, sys_path
    content = {}
    try:
        exec_function('import %s as module' % name, content)
        module = content['module']
    except AttributeError:
        # use sys.modules, because you cannot access some modules
        # directly. -> github issue #59
        module = sys.modules[name]
    except ImportError:
        name = get_parent_until(path)
        if name in sys.modules:
            module = sys.modules[name]
        else:
            module = __import__(name, fromlist=[name.rpartition('.')[-1]])
    sys.path = temp

    return PyObject(module)


docstr_defaults = {
    'floating point number': 'float',
    'character': 'str',
    'integer': 'int',
    'dictionary': 'dict',
    'string': 'str',
}

if is_py3k:
    #docstr_defaults['file object'] = 'import io; return io.TextIOWrapper()'
    pass  # TODO reenable
else:
    docstr_defaults['file object'] = 'file'


def _parse_function_doc(doc):
    """
    Takes a function and returns the params and return value as a tuple.
    This is nothing more than a docstring parser.

    TODO docstrings like utime(path, (atime, mtime)) and a(b [, b]) -> None
    TODO docstrings like 'tuple of integers'
    """

    # parse round parentheses: def func(a, (b,c))
    try:
        count = 0
        start = doc.index('(')
        for i, s in enumerate(doc[start:]):
            if s == '(':
                count += 1
            elif s == ')':
                count -= 1
            if count == 0:
                end = start + i
                break
        param_str = doc[start + 1:end]
    except (ValueError, UnboundLocalError):
        # ValueError for doc.index
        # UnboundLocalError for undefined end in last line
        debug.dbg('no brackets found - no param')
        end = 0
        param_str = ''
    else:
        # remove square brackets, that show an optional param ( = None)
        def change_options(m):
            args = m.group(1).split(',')
            for i, a in enumerate(args):
                if a and '=' not in a:
                    args[i] += '=None'
            return ','.join(args)

        while True:
            param_str, changes = re.subn(r' ?\[([^\[\]]+)\]',
                                         change_options, param_str)
            if changes == 0:
                break
    param_str = param_str.replace('-', '_')  # see: isinstance.__doc__

    # parse return value
    r = re.search('-[>-]* ', doc[end:end + 7])
    if r is None:
        ret = ''
    else:
        index = end + r.end()
        # get result type, which can contain newlines
        pattern = re.compile(r'(,\n|[^\n-])+')
        ret_str = pattern.match(doc, index).group(0).strip()
        # New object -> object()
        ret_str = re.sub(r'[nN]ew (.*)', r'\1()', ret_str)

        ret = docstr_defaults.get(ret_str, ret_str)

    return param_str, ret


builtin = PyObject(_builtins)
magic_function_class = PyObject(type(load_module), parent=builtin)


def create(obj):
    return PyObject(obj, builtin)
