import re
import sys
import os

import debug
import parsing


class Parser(object):
    """
    This module is a parser for all builtin modules, which are programmed in
    C/C++. It should also work on third party modules.
    It can be instantiated with either a path or a name of the module. The path
    is important for third party modules.

    TODO maybe remove some code and merge it with `modules`?

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
        'object': '{}',
        # TODO things like dbg: ('not working', 'tuple of integers')
    }
    cache = {}

    def __init__(self, name=None, path=None, sys_path=sys.path):
        self.path = path
        if name:
            self.name = name
        else:
            name = os.path.basename(self.path)
            self.name = name.rpartition('.')[0]  # cut file type (normally .so)
            self.path = os.path.dirname(self.path)
            #print self.name, self.path
        self._content = {}
        self._parser = None
        self._module = None
        self.sys_path = sys_path

    @property
    def module(self):
        if not self._module:
            self.sys_path.insert(0, self.path)

            temp, sys.path = sys.path, self.sys_path
            #print 'sypa', sys.path TODO reenable and check (stackoverflow ticket)
            exec 'import %s as module' % self.name in self._content
            self.sys_path, sys.path = sys.path, temp

            self.sys_path.pop(0)
            self._module = self._content['module']
            #print 'mod', self._content['module']
        return self._module

    @property
    def parser(self):
        """ get the parser lazy """
        if not self._parser:
            try:
                timestamp, parser = Parser.cache[self.name, self.path]
                if not self.path or timestamp == os.path.getmtime(self.path):
                    debug.dbg('hit builtin cache')
                    self._parser = parser
                else:
                    raise KeyError
            except KeyError:
                code = self._generate_code(self.module)
                try:
                    self._parser = parsing.PyFuzzyParser(code)
                except:
                    debug.warning('not possible to resolve', self.name, code)
                    #open('builtin_fail', 'w').write(code)
                    raise
                else:
                    if self.path:
                        p_time = os.path.getmtime(self.path)
                    else:
                        p_time = None
                    Parser.cache[self.name, self.path] = p_time, self._parser
        return self._parser

    def _generate_code(self, scope, depth=0):
        """
        Generate a string, which uses python syntax as an input to the
        PyFuzzyParser.
        """
        def get_types(names):
            classes = {}
            funcs = {}
            stmts = {}
            members = {}
            for n in names:
                if '__' in n:
                    continue
                # this has a builtin_function_or_method
                exe = getattr(scope, n)
                if type(exe).__name__ in ['method_descriptor',
                                            'builtin_function_or_method']:
                    funcs[n] = exe
                elif type(exe) == type:
                    classes[n] = exe
                elif type(exe).__name__ == 'member_descriptor':
                    members[n] = exe
                else:
                    stmts[n] = exe
            return classes, funcs, stmts, members

        code = ''
        try:
            try:
                path = scope.__file__
            except:
                path = '?'
            code += '# Generated module %s from %s\n' % (scope.__name__, path)
        except:
            pass
        code += '"""\n%s\n"""\n' % scope.__doc__

        names = set(dir(scope)) - set(['__file__', '__name__', '__doc__',
                                    '__path__', '__package__'])
        classes, funcs, stmts, members = get_types(names)

        # classes
        for name, cl in classes.iteritems():
            bases = (c.__name__ for c in cl.__bases__)
            code += 'class %s(%s):\n' % (name, ','.join(bases))
            if depth == 0:
                cl_code = self._generate_code(cl, depth + 1)
                code += parsing.indent_block(cl_code)
            code += '\n'

        # functions
        for name, func in funcs.iteritems():
            params, ret = parse_function_doc(func)
            code += 'def %s(%s):\n' % (name, params)
            block = '"""\n%s\n"""\n' % func.__doc__
            block += '%s\n\n' % ret
            code += parsing.indent_block(block)

        # class members (functions)
        for name, func in members.iteritems():
            ret = 'pass'
            code += '@property\ndef %s(self):\n' % (name)
            block = '"""\n%s\n"""\n' % func.__doc__
            block += '%s\n\n' % ret
            code += parsing.indent_block(block)

        # variables
        for name, value in stmts.iteritems():
            if type(value) == file:
                value = 'file'
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
    doc = func.__doc__

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

        # remove square brackets, which show an optional param ( in Python = None)
        def change_options(m):
            args = m.group(1).split(',')
            for i, a in enumerate(args):
                if a and '=' not in a:
                    args[i] += '=None'
            return ','.join(args)
        while True:
            (param_str, changes) = re.subn(r' ?\[([^\[\]]+)\]',
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
            ret = 'return ' + ret
    return param_str, ret


class _Builtin(object):
    _builtins = Parser(name='__builtin__')

    @property
    def scope(self):
        return self._builtins.parser.top


Builtin = _Builtin()
