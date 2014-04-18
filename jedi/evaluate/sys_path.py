import os
import sys

from jedi._compatibility import exec_function, unicode
from jedi.parser import representation as pr
from jedi import debug
from jedi import common


def get_sys_path():
    def check_virtual_env(sys_path):
        """ Add virtualenv's site-packages to the `sys.path`."""
        venv = os.getenv('VIRTUAL_ENV')
        if not venv:
            return
        venv = os.path.abspath(venv)
        p = os.path.join(
            venv, 'lib', 'python%d.%d' % sys.version_info[:2], 'site-packages')
        sys_path.insert(0, p)

    check_virtual_env(sys.path)
    return [p for p in sys.path if p != ""]


#@cache.memoize_default([]) TODO add some sort of cache again.
def sys_path_with_modifications(module):
    def execute_code(code):
        c = "import os; from os.path import *; result=%s"
        variables = {'__file__': module.path}
        try:
            exec_function(c % code, variables)
        except Exception:
            debug.warning('sys.path manipulation detected, but failed to evaluate.')
            return None
        try:
            res = variables['result']
            if isinstance(res, str):
                return os.path.abspath(res)
            else:
                return None
        except KeyError:
            return None

    def check_module(module):
        try:
            possible_stmts = module.used_names['path']
        except KeyError:
            return get_sys_path()

        sys_path = list(get_sys_path())  # copy
        for p in possible_stmts:
            if not isinstance(p, pr.Statement):
                continue
            expression_list = p.expression_list()
            # sys.path command is just one thing.
            if len(expression_list) != 1 or not isinstance(expression_list[0], pr.Call):
                continue
            call = expression_list[0]
            n = call.name
            if not isinstance(n, pr.Name) or len(n.names) != 3:
                continue
            if [unicode(x) for x in n.names[:2]] != ['sys', 'path']:
                continue
            array_cmd = unicode(n.names[2])
            if call.execution is None:
                continue
            exe = call.execution
            if not (array_cmd == 'insert' and len(exe) == 2
                    or array_cmd == 'append' and len(exe) == 1):
                continue

            if array_cmd == 'insert':
                exe_type, exe.type = exe.type, pr.Array.NOARRAY
                exe_pop = exe.values.pop(0)
                res = execute_code(exe.get_code())
                if res is not None:
                    sys_path.insert(0, res)
                    debug.dbg('sys path inserted: %s', res)
                exe.type = exe_type
                exe.values.insert(0, exe_pop)
            elif array_cmd == 'append':
                res = execute_code(exe.get_code())
                if res is not None:
                    sys_path.append(res)
                    debug.dbg('sys path added: %s', res)
        return sys_path

    if module.path is None:
        # Support for modules without a path is bad, therefore return the
        # normal path.
        return list(get_sys_path())

    curdir = os.path.abspath(os.curdir)
    with common.ignored(OSError):
        os.chdir(os.path.dirname(module.path))

    result = check_module(module)
    result += _detect_django_path(module.path)

    # cleanup, back to old directory
    os.chdir(curdir)
    return result


def _detect_django_path(module_path):
    """ Detects the path of the very well known Django library (if used) """
    result = []
    while True:
        new = os.path.dirname(module_path)
        # If the module_path doesn't change anymore, we're finished -> /
        if new == module_path:
            break
        else:
            module_path = new

        with common.ignored(IOError):
            with open(module_path + os.path.sep + 'manage.py'):
                debug.dbg('Found django path: %s', module_path)
                result.append(module_path)
    return result
