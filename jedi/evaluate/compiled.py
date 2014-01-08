"""
Imitate the parser representation.
"""
import inspect
import re

from jedi._compatibility import builtins as _builtins, is_py3k
from jedi import debug
from jedi.cache import underscore_memoization


# TODO
# unbound methods such as pyqtSignals have no __name__
# if not hasattr(func, "__name__"):

class PyObject(object):
    def __init__(self, obj, parent=None, instantiated=False):
        self.obj = obj
        self.parent = parent
        self.instantiated = instantiated
        self.doc = inspect.getdoc(obj)

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.obj)

    @underscore_memoization
    def _parse_function_doc(self):
        if self.doc is None:
            return '', ''

        return _parse_function_doc(self.doc)

    def get_defined_names(self):
        # We don't want to execute properties, therefore we have to try to get
        # the class
        cls = self
        if not (inspect.isclass(self.obj) or inspect.ismodule(self.obj)):
            cls = PyObject(self.obj.__class__, self.parent)

        for name in dir(cls.obj):
            yield PyName(cls, name)

    def isinstance(self, *obj):
        return isinstance(self, obj)

    @property
    def name(self):
        # might not exist sometimes (raises AttributeError)
        return self.obj.__name__

    def execute(self, params):
        if inspect.isclass(self.obj):
            yield PyObject(self.obj, self.parent, True)
        elif inspect.isbuiltin(self.obj) or inspect.ismethod(self.obj) \
                or inspect.ismethoddescriptor(self.obj):
            for name in self._parse_function_doc()[1].split():
                try:
                    yield PyObject(getattr(_builtins, name), builtin, True)
                except AttributeError:
                    pass


class PyName(object):
    def __init__(self, obj, name):
        self._obj = obj
        self._name = name

        self.start_pos = 0, 0  # an illegal start_pos, to make sorting easy.

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

    def get_code(self):
        return self._name


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
