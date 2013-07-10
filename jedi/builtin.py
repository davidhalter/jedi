"""
A big part of the Python standard libraries are unfortunately not only written
in Python. The process works like this:

- ``BuiltinModule`` imports the builtin module (e.g. ``sys``)
- then ``BuiltinModule`` generates code with the docstrings of builtin
  functions.
- The :mod:`parsing` parser processes the generated code.

This is possible, because many builtin functions supply docstrings, for example
the method ``list.index`` has the following attribute ``__doc__``:

    L.index(value, [start, [stop]]) -> integer -- return first index of value.
        Raises ValueError if the value is not present.

`PEP 257 <http://www.python.org/dev/peps/pep-0257/#one-line-docstrings>`_
teaches how docstrings should look like for C functions.

Additionally there's a ``Builtin``  instance in this module, to make it
possible to access functions like ``list`` and ``int`` directly, the same way
|jedi| access other functions.
"""

from __future__ import with_statement
from jedi._compatibility import exec_function, is_py3k

import re
import sys
import os
if is_py3k:
    import io
import types
import inspect

from jedi import common
from jedi import debug
from jedi import parsing
from jedi import modules
import evaluate


class BuiltinModule(modules.CachedModule):
    """
    This module is a parser for all builtin modules, which are programmed in
    C/C++. It should also work on third party modules.
    It can be instantiated with either a path or a name of the module. The path
    is important for third party modules.

    :param name: The name of the module.
    :param path: The path of the module.
    :param sys_path: The sys.path, which is can be customizable.
    """

    map_types = {
        'floating point number': '0.0',
        'string': '""',
        'str': '""',
        'character': '"a"',
        'integer': '0',
        'int': '0',
        'dictionary': '{}',
        'list': '[]',
        'file object': 'file("")',
        # TODO things like dbg: ('not working', 'tuple of integers')
    }

    if is_py3k:
        map_types['file object'] = 'import io; return io.TextIOWrapper()'

    def __init__(self, path=None, name=None, sys_path=None):
        if sys_path is None:
            sys_path = modules.get_sys_path()
        if not name:
            name = os.path.basename(path)
            name = name.rpartition('.')[0]  # cut file type (normally .so)
        super(BuiltinModule, self).__init__(path=path, name=name)

        self.sys_path = list(sys_path)
        self._module = None

    @property
    def module(self):
        def load_module(name, path):
            if path:
                self.sys_path.insert(0, path)

            temp, sys.path = sys.path, self.sys_path
            content = {}
            try:
                exec_function('import %s as module' % name, content)
                self._module = content['module']
            except AttributeError:
                # use sys.modules, because you cannot access some modules
                # directly. -> #59
                self._module = sys.modules[name]
            sys.path = temp

            if path:
                self.sys_path.pop(0)

        # module might already be defined
        if not self._module:
            path = self.path
            name = self.name
            if self.path:

                dot_path = []
                p = self.path
                # search for the builtin with the correct path
                while p and p not in sys.path:
                    p, sep, mod = p.rpartition(os.path.sep)
                    dot_path.append(mod.partition('.')[0])
                if p:
                    name = ".".join(reversed(dot_path))
                    path = p
                else:
                    path = os.path.dirname(self.path)

            load_module(name, path)
        return self._module

    def _get_source(self):
        """ Override this abstract method """
        return _generate_code(self.module, self._load_mixins())

    def _load_mixins(self):
        """
        Load functions that are mixed in to the standard library.
        E.g. builtins are written in C (binaries), but my autocompletion only
        understands Python code. By mixing in Python code, the autocompletion
        should work much better for builtins.
        """
        regex = r'^(def|class)\s+([\w\d]+)'

        def process_code(code, depth=0):
            funcs = {}
            matches = list(re.finditer(regex, code, re.MULTILINE))
            positions = [m.start() for m in matches]
            for i, pos in enumerate(positions):
                try:
                    code_block = code[pos:positions[i + 1]]
                except IndexError:
                    code_block = code[pos:len(code)]
                structure_name = matches[i].group(1)
                name = matches[i].group(2)
                if structure_name == 'def':
                    funcs[name] = code_block
                elif structure_name == 'class':
                    if depth > 0:
                        raise NotImplementedError()

                    # remove class line
                    c = re.sub(r'^[^\n]+', '', code_block)
                    # remove whitespace
                    c = re.compile(r'^[ ]{4}', re.MULTILINE).sub('', c)

                    funcs[name] = process_code(c)
                else:
                    raise NotImplementedError()
            return funcs

        try:
            name = self.name
            # sometimes there are stupid endings like `_sqlite3.cpython-32mu`
            name = re.sub(r'\..*', '', name)

            if name == '__builtin__' and not is_py3k:
                name = 'builtins'
            path = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.sep.join([path, 'mixin', name]) + '.pym') as f:
                s = f.read()
        except IOError:
            return {}
        else:
            mixin_dct = process_code(s)
            if is_py3k and self.name == Builtin.name:
                # in the case of Py3k xrange is now range
                mixin_dct['range'] = mixin_dct['xrange']
            return mixin_dct


def _generate_code(scope, mixin_funcs={}, depth=0):
    """
    Generate a string, which uses python syntax as an input to the Parser.
    """
    def get_doc(obj, indent=False):
        doc = inspect.getdoc(obj)
        if doc:
            doc = ('r"""\n%s\n"""\n' % doc)
            if indent:
                doc = common.indent_block(doc)
            return doc
        return ''

    def is_in_base_classes(cls, name, comparison):
        """ Base classes may contain the exact same object """
        if name in mixin_funcs:
            return False
        try:
            mro = cls.mro()
        except TypeError:
            # this happens, if cls == type
            return False
        for base in mro[1:]:
            try:
                attr = getattr(base, name)
            except AttributeError:
                continue
            if attr == comparison:
                return True
        return False

    def get_scope_objects(names):
        """
        Looks for the names defined with dir() in an objects and divides
        them into different object types.
        """
        classes = {}
        funcs = {}
        stmts = {}
        members = {}
        for n in names:
            try:
                # this has a builtin_function_or_method
                exe = getattr(scope, n)
            except AttributeError:
                # happens e.g. in properties of
                # PyQt4.QtGui.QStyleOptionComboBox.currentText
                # -> just set it to None
                members[n] = None
            else:
                if inspect.isclass(scope):
                    if is_in_base_classes(scope, n, exe):
                        continue
                if inspect.isbuiltin(exe) or inspect.ismethod(exe) \
                        or inspect.ismethoddescriptor(exe):
                    funcs[n] = exe
                elif inspect.isclass(exe) or inspect.ismodule(exe):
                    classes[n] = exe
                elif inspect.ismemberdescriptor(exe):
                    members[n] = exe
                else:
                    stmts[n] = exe
        return classes, funcs, stmts, members

    code = ''
    if inspect.ismodule(scope):  # generate comment where the code's from.
        try:
            path = scope.__file__
        except AttributeError:
            path = '?'
        code += '# Generated module %s from %s\n' % (scope.__name__, path)

    code += get_doc(scope)

    names = set(dir(scope)) - set(['__file__', '__name__', '__doc__',
                                   '__path__', '__package__']) \
        | set(['mro'])

    classes, funcs, stmts, members = get_scope_objects(names)

    # classes
    for name, cl in classes.items():
        bases = (c.__name__ for c in cl.__bases__) if inspect.isclass(cl) \
            else []
        code += 'class %s(%s):\n' % (name, ','.join(bases))
        if depth == 0:
            try:
                mixin = mixin_funcs[name]
            except KeyError:
                mixin = {}
            cl_code = _generate_code(cl, mixin, depth + 1)
            code += common.indent_block(cl_code)
        code += '\n'

    # functions
    for name, func in funcs.items():
        params, ret = _parse_function_doc(func)
        if depth > 0:
            params = 'self, ' + params
        doc_str = get_doc(func, indent=True)
        try:
            mixin = mixin_funcs[name]
        except KeyError:
            # normal code generation
            code += 'def %s(%s):\n' % (name, params)
            code += doc_str
            code += common.indent_block('%s\n\n' % ret)
        else:
            # generation of code with mixins
            # the parser only supports basic functions with a newline after
            # the double dots
            # find doc_str place
            try:
                pos = re.search(r'\):\s*\n', mixin).end()
            except TypeError:
                # pypy uses a different reversed builtin
                if name == 'reversed':
                    mixin = 'def reversed(sequence):\n' \
                            '    for i in self.__sequence: yield i'
                    pos = 24
                else:
                    debug.warning('mixin trouble in pypy: %s', name)
                    raise
            if pos is None:
                raise Exception("Builtin function not parsed correctly")
            code += mixin[:pos] + doc_str + mixin[pos:]

    # class members (functions) properties?
    for name, func in members.items():
        # recursion problem in properties TODO remove
        if name in ['fget', 'fset', 'fdel']:
            continue
        ret = 'pass'
        code += '@property\ndef %s(self):\n' % (name)
        code += common.indent_block(get_doc(func) + '%s\n\n' % ret)

    # variables
    for name, value in stmts.items():
        if is_py3k:
            file_type = io.TextIOWrapper
        else:
            file_type = types.FileType
        if isinstance(value, file_type):
            value = 'open()'
        elif name == 'None':
            value = ''
        elif type(value).__name__ in ['int', 'bool', 'float',
                                      'dict', 'list', 'tuple']:
            value = repr(value)
        else:
            # get the type, if the type is not simple.
            mod = type(value).__module__
            value = type(value).__name__ + '()'
            if mod != '__builtin__':
                value = '%s.%s' % (mod, value)
        code += '%s = %s\n' % (name, value)

    return code


def _parse_function_doc(func):
    """
    Takes a function and returns the params and return value as a tuple.
    This is nothing more than a docstring parser.
    """
    # TODO: things like utime(path, (atime, mtime)) and a(b [, b]) -> None
    doc = inspect.getdoc(func)

    # get full string, parse round parentheses: def func(a, (b,c))
    try:
        count = 0
        debug.dbg(func, func.__name__, doc)
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
    except (ValueError, AttributeError):
        debug.dbg('no brackets found - no param')
        end = 0
        param_str = ''

    param_str = param_str.replace('-', '_')  # see: isinstance.__doc__

    if doc is not None:
        r = re.search('-[>-]* ', doc[end:end + 7])
    if doc is None or r is None:
        ret = 'pass'
    else:
        index = end + r.end()
        # get result type, which can contain newlines
        pattern = re.compile(r'(,\n|[^\n-])+')
        ret_str = pattern.match(doc, index).group(0).strip()
        # New object -> object()
        ret_str = re.sub(r'[nN]ew (.*)', r'\1()', ret_str)

        ret = BuiltinModule.map_types.get(ret_str, ret_str)
        if ret == ret_str and ret not in ['None', 'object', 'tuple', 'set']:
            debug.dbg('not working', ret_str)
        if ret != 'pass':
            ret = ('return ' if 'return' not in ret else '') + ret
    return param_str, ret


class Builtin(object):
    """ The builtin scope / module """
    # Python 3 compatibility
    if is_py3k:
        name = 'builtins'
    else:
        name = '__builtin__'

    _builtin = None

    @property
    def builtin(self):
        if self._builtin is None:
            self._builtin = BuiltinModule(name=self.name)
        return self._builtin

    @property
    def scope(self):
        return self.builtin.parser.module

    @property
    def magic_function_scope(self):
        try:
            return self._magic_function_scope
        except AttributeError:
            # depth = 1 because this is not a module
            class Container(object):
                FunctionType = types.FunctionType
            source = _generate_code(Container, depth=0)
            parser = parsing.Parser(source, None)
            module = parser.module
            module.parent = self.scope
            typ = evaluate.follow_path(iter(['FunctionType']), module, module)

            s = self._magic_function_scope = typ.pop()
            return s


Builtin = Builtin()
