import os
import sys

from jedi._compatibility import exec_function, unicode
from jedi.parser import representation as pr
from jedi.parser import Parser
from jedi.evaluate.cache import memoize_default
from jedi import debug
from jedi import common


def get_sys_path():
    def check_virtual_env(sys_path):
        """ Add virtualenv's site-packages to the `sys.path`."""
        venv = os.getenv('VIRTUAL_ENV')
        if not venv:
            return
        venv = os.path.abspath(venv)
        if os.name == 'nt':
            p = os.path.join(venv, 'lib', 'site-packages')
        else:
            p = os.path.join(venv, 'lib', 'python%d.%d' % sys.version_info[:2],
                             'site-packages')
        if p not in sys_path:
            sys_path.insert(0, p)

    check_virtual_env(sys.path)
    return [p for p in sys.path if p != ""]


def _execute_code(module_path, code):
    c = "import os; from os.path import *; result=%s"
    variables = {'__file__': module_path}
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


def _paths_from_assignment(statement):
    """
    extracts the assigned strings from an assignment that looks as follows::

    >>> sys.path[0:0] = ['module/path', 'another/module/path']
    """

    names = statement.get_defined_names()
    if len(names) != 1:
        return []
    if [unicode(x) for x in names[0].names] != ['sys', 'path']:
        return []
    expressions = statement.expression_list()
    if len(expressions) != 1 or not isinstance(expressions[0], pr.Array):
        return
    stmts = (s for s in expressions[0].values if isinstance(s, pr.Statement))
    expression_lists = (s.expression_list() for s in stmts)
    return [e.value for exprs in expression_lists for e in exprs
            if isinstance(e, pr.Literal) and e.value]


def _paths_from_insert(module_path, exe):
    """ extract the inserted module path from an "sys.path.insert" statement
    """
    exe_type, exe.type = exe.type, pr.Array.NOARRAY
    exe_pop = exe.values.pop(0)
    res = _execute_code(module_path, exe.get_code())
    exe.type = exe_type
    exe.values.insert(0, exe_pop)
    return res


def _paths_from_call_expression(module_path, call):
    """ extract the path from either "sys.path.append" or "sys.path.insert" """
    if call.execution is None:
        return
    n = call.name
    if not isinstance(n, pr.Name) or len(n.names) != 3:
        return
    names = [unicode(x) for x in n.names]
    if names[:2] != ['sys', 'path']:
        return
    cmd = names[2]
    exe = call.execution
    if cmd == 'insert' and len(exe) == 2:
        path = _paths_from_insert(module_path, exe)
    elif cmd == 'append' and len(exe) == 1:
        path = _execute_code(module_path, exe.get_code())
    return path and [path] or []


def _check_module(module):
    try:
        possible_stmts = module.used_names['path']
    except KeyError:
        return get_sys_path()
    sys_path = list(get_sys_path())  # copy
    statements = (p for p in possible_stmts if isinstance(p, pr.Statement))
    for stmt in statements:
        expressions = stmt.expression_list()
        if len(expressions) == 1 and isinstance(expressions[0], pr.Call):
            sys_path.extend(
                _paths_from_call_expression(module.path, expressions[0]) or [])
        elif (
            hasattr(stmt, 'assignment_details') and
            len(stmt.assignment_details) == 1
        ):
            sys_path.extend(_paths_from_assignment(stmt) or [])
    return sys_path


@memoize_default(evaluator_is_first_arg=True)
def sys_path_with_modifications(evaluator, module):
    if module.path is None:
        # Support for modules without a path is bad, therefore return the
        # normal path.
        return list(get_sys_path())

    curdir = os.path.abspath(os.curdir)
    with common.ignored(OSError):
        os.chdir(os.path.dirname(module.path))

    result = _check_module(module)
    result += _detect_django_path(module.path)
    # buildout scripts often contain the same sys.path modifications
    # the set here is used to avoid duplicate sys.path entries
    buildout_paths = set()
    for module_path in _get_buildout_scripts(module.path):
        try:
            with open(module_path, 'rb') as f:
                source = f.read()
        except IOError:
            pass
        else:
            p = Parser(common.source_to_unicode(source), module_path)
            for path in _check_module(p.module):
                if path not in buildout_paths:
                    buildout_paths.add(path)
                    result.append(path)
    # cleanup, back to old directory
    os.chdir(curdir)
    return list(result)


def _traverse_parents(path):
    while True:
        new = os.path.dirname(path)
        if new == path:
            return
        path = new
        yield path


def _get_parent_dir_with_file(path, filename):
    for parent in _traverse_parents(path):
        if os.path.isfile(os.path.join(parent, filename)):
            return parent
    return None


def _detect_django_path(module_path):
    """ Detects the path of the very well known Django library (if used) """
    result = []

    for parent in _traverse_parents(module_path):
        with common.ignored(IOError):
            with open(parent + os.path.sep + 'manage.py'):
                debug.dbg('Found django path: %s', module_path)
                result.append(parent)
    return result


def _get_buildout_scripts(module_path):
    """
    if there is a 'buildout.cfg' file in one of the parent directories of the
    given module it will return a list of all files in the buildout bin
    directory that look like python files.

    :param module_path: absolute path to the module.
    :type module_path: str
    """
    project_root = _get_parent_dir_with_file(module_path, 'buildout.cfg')
    if not project_root:
        return []
    bin_path = os.path.join(project_root, 'bin')
    if not os.path.exists(bin_path):
        return []
    extra_module_paths = []
    for filename in os.listdir(bin_path):
        try:
            filepath = os.path.join(bin_path, filename)
            with open(filepath, 'r') as f:
                firstline = f.readline()
                if firstline.startswith('#!') and 'python' in firstline:
                    extra_module_paths.append(filepath)
        except IOError as e:
            # either permission error or race cond. because file got deleted
            # ignore
            debug.warning(unicode(e))
            continue
    return extra_module_paths
