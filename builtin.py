import re

import debug
import parsing


class Parser(object):
    map_types = {
        'floating point number': '0.0',
        'string': '""',
        'str': '""',
        'integer': '0',
        'int': '0',
        'dictionary': '{}',
        'list': '[]',
        'object': '{}',
        # TODO things like dbg: ('not working', 'tuple of integers')
    }

    """ This module tries to imitate parsing.Scope """
    def __init__(self, name):
        self.name = name
        self.parent = None
        self.content = {}
        exec 'import %s as module' % name in self.content
        self.module = self.content['module']
        self._parser = None

    @property
    def parser(self):
        """ get the parser lazy """
        if self._parser:
            return self._parser
        else:
            code = self.generate_code(self.module)
            try:
                self._parser = parsing.PyFuzzyParser(code)
            except:
                debug.warning('not possible to resolve', self.name, code)
                #open('builtin_fail', 'w').write(code)
                raise
            return self._parser

    def generate_code(self, scope, depth=0):
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
                if type(exe).__name__ == 'builtin_function_or_method':
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

        names = set(dir(scope)) - {'__file__', '__name__', '__doc__',
                                    '__path__', '__package__'}
        classes, funcs, stmts, members = get_types(names)
        #print 'blub', get_types(names)

        # classes
        for name, cl in classes.iteritems():
            bases = (c.__name__ for c in cl.__bases__)
            code += 'class %s(%s):\n' % (name, ','.join(bases))
            if depth == 0:
                cl_code = self.generate_code(cl, depth + 1)
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
            if isinstance(value, str):
                value = repr(value)
            elif type(value) == file:
                value = 'file'
            code += '%s = %s\n' % (name, value)

        import sys
        #if depth == 0:
        #    sys.stdout.write(code)
        #    exit()
        return code


def parse_function_doc(func):
    """
    Takes a function and returns the params and return value as a tuple.
    This is nothing more than a docstring parser.
    """
    # TODO: things like utime(path, (atime, mtime)) and a(b [, b]) -> None
    params = []
    doc = func.__doc__
    end = doc.index(')')
    #print 'blubedi', doc
    param_str = doc[doc.index('(') + 1:end]
    try:
        index = doc.index('-> ', end, end + 7)
    except ValueError:
        ret = 'pass'
    else:
        pattern = re.compile(r'(,\n|[^\n])+')
        ret_str = pattern.match(doc, index + 3).group(0)
        ret = Parser.map_types.get(ret_str, ret_str)
        if ret == ret_str and ret not in ['None', 'object', 'tuple', 'set']:
            debug.dbg('not working', ret_str)
        if ret != 'pass':
            ret = 'return ' + ret
    return param_str, ret

"""if current.arr_type == parsing.Array.EMPTY:
    # the normal case - no array type
    print 'length', len(current)
elif current.arr_type == parsing.Array.LIST:
    result.append(__builtin__.list())
elif current.arr_type == parsing.Array.SET:
    result.append(__builtin__.set())
elif current.arr_type == parsing.Array.TUPLE:
    result.append(__builtin__.tuple())
elif current.arr_type == parsing.Array.DICT:
    result.append(__builtin__.dict())
    """
