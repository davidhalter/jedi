import re
import sys
import os
import types
if sys.hexversion >= 0x03000000:
    import io
import inspect

import debug
import parsing

from _compatibility import exec_function

module_find_path = sys.path[1:]


class CachedModule(object):
    cache = {}

    def __init__(self, path=None, name=None):
        self.path = path
        self.name = name
        self._parser = None

    @property
    def parser(self):
        """ get the parser lazy """
        if not self._parser:
            try:
                timestamp, parser = self.cache[self.path or self.name]
                if not self.path or timestamp == os.path.getmtime(self.path):
                    self._parser = parser
                else:
                    raise KeyError
            except KeyError:
                self._load_module()
        return self._parser

    def _get_source(self):
        raise NotImplementedError()

    def _load_module(self):
        source = self._get_source()
        self._parser = parsing.PyFuzzyParser(source, self.path or self.name)
        p_time = None if not self.path else os.path.getmtime(self.path)

        self.cache[self.path or self.name] = p_time, self._parser


class Parser(CachedModule):
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

    if sys.hexversion >= 0x03000000:
        map_types['file object'] = 'import io; return io.TextIOWrapper(file)'

    module_cache = {}

    def __init__(self, path=None, name=None, sys_path=module_find_path):
        if not name:
            name = os.path.basename(path)
            name = name.rpartition('.')[0]  # cut file type (normally .so)
        super(Parser, self).__init__(path=path, name=name)

        self.sys_path = sys_path
        self._content = {}
        self._module = None

    @property
    def module(self):
        if not self._module:
            self.sys_path.insert(0, self.path)

            temp, sys.path = sys.path, self.sys_path
            # TODO reenable and check (stackoverflow question - pylab builtins)
            #print 'sypa', sys.path
            exec_function('import %s as module' % self.name, self._content)

            self.sys_path, sys.path = sys.path, temp

            self.sys_path.pop(0)
            self._module = self._content['module']
            #print 'mod', self._content['module']
        return self._module

    def _get_source(self):
        return self._generate_code(self.module, self._load_mixins())

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
            if name == '__builtin__' and sys.hexversion < 0x03000000:
                name = 'builtins'
            f = open(os.path.sep.join(['mixin', name]) + '.py')
        except IOError:
            return {}
        else:
            return process_code(f.read())

    def _generate_code(self, scope, mixin_funcs, depth=0):
        """
        Generate a string, which uses python syntax as an input to the
        PyFuzzyParser.
        """
        def get_doc(obj, indent=False):
            doc = inspect.getdoc(obj)
            if doc:
                doc = ('"""\n%s\n"""\n' % doc)
                if indent:
                    doc = parsing.indent_block(doc)
                return doc
            return ''

        def get_types(names):
            classes = {}
            funcs = {}
            stmts = {}
            members = {}
            for n in names:
                if '__' in n and n not in mixin_funcs:
                    continue
                # this has a builtin_function_or_method
                exe = getattr(scope, n)
                if inspect.isbuiltin(exe) or inspect.ismethoddescriptor(exe):
                    funcs[n] = exe
                elif inspect.isclass(exe):
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
                                                '__path__', '__package__'])

        classes, funcs, stmts, members = get_types(names)

        # classes
        for name, cl in classes.items():
            bases = (c.__name__ for c in cl.__bases__)
            code += 'class %s(%s):\n' % (name, ','.join(bases))
            if depth == 0:
                try:
                    mixin = mixin_funcs[name]
                except KeyError:
                    mixin = {}
                cl_code = self._generate_code(cl, mixin, depth + 1)
                code += parsing.indent_block(cl_code)
            code += '\n'

        # functions
        for name, func in funcs.items():
            params, ret = parse_function_doc(func)
            doc_str = get_doc(func, indent=True)
            try:
                mixin = mixin_funcs[name]
            except KeyError:
                # normal code generation
                code += 'def %s(%s):\n' % (name, params)
                code += doc_str
                code += parsing.indent_block('%s\n\n' % ret)
            else:
                # generation of code with mixins
                # the parser only supports basic functions with a newline after
                # the double dots
                # find doc_str place
                pos = re.search(r'\):\s*\n', mixin).end()
                if pos is None:
                    raise Exception("Builtin function not parsed correctly")
                code += mixin[:pos] + doc_str + mixin[pos:]

        # class members (functions) properties?
        for name, func in members.items():
            # recursion problem in properties TODO remove
            if name in ['fget', 'fset', 'fdel']: continue
            ret = 'pass'
            code += '@property\ndef %s(self):\n' % (name)
            code += parsing.indent_block(get_doc(func) + '%s\n\n' % ret)

        # variables
        for name, value in stmts.items():
            if sys.hexversion >= 0x03000000:
                file_type = io.TextIOWrapper
            else:
                file_type = types.FileType
            if type(value) == file_type:
                value = 'open()'
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

        if depth == 0:
            #with open('writeout.py', 'w') as f:
            #    f.write(code)
            #import sys
            #sys.stdout.write(code)
            #exit()
            pass
        return code


def parse_function_doc(func):
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

    try:
        index = doc.index('-> ', end, end + 7)
    except (ValueError, AttributeError):
        ret = 'pass'
    else:
        # get result type, which can contain newlines
        pattern = re.compile(r'(,\n|[^\n-])+')
        ret_str = pattern.match(doc, index + 3).group(0)
        ret = Parser.map_types.get(ret_str, ret_str)
        if ret == ret_str and ret not in ['None', 'object', 'tuple', 'set']:
            debug.dbg('not working', ret_str)
        if ret != 'pass':
            ret = ('return ' if 'return' not in ret else '') + ret
    return param_str, ret


class _Builtin(object):
    # Python 3 compatibility
    if sys.hexversion >= 0x03000000:
        name = 'builtins'
    else:
        name = '__builtin__'
    _builtins = Parser(name=name)

    @property
    def scope(self):
        return self._builtins.parser.top

    def get_defined_names(self):
        return self.scope.get_defined_names()


Builtin = _Builtin()
