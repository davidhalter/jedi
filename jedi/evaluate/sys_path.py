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
    else:
        try:
            res = variables['result']
            if isinstance(res, str):
                return [os.path.abspath(res)]
        except KeyError:
            pass
    return []


def _paths_from_assignment(evaluator, statement):
    """
    Extracts the assigned strings from an assignment that looks as follows::

    >>> sys.path[0:0] = ['module/path', 'another/module/path']

    This function is in general pretty tolerant (and therefore 'buggy').
    However, it's not a big issue usually to add more paths to Jedi's sys_path,
    because it will only affect Jedi in very random situations and by adding
    more paths than necessary, it usually benefits the general user.
    """
    for exp_list, operator in statement.assignment_details:
        if len(exp_list) != 1 or not isinstance(exp_list[0], pr.Call):
            continue
        if exp_list[0].names() != ['sys', 'path']:
            continue
        # TODO at this point we ignore all ways what could be assigned to
        # sys.path or an execution of it. Here we could do way more
        # complicated checks.

        from jedi.evaluate.iterable import get_iterator_types
        from jedi.evaluate.precedence import is_string
        for val in get_iterator_types(evaluator.eval_statement(statement)):
            if is_string(val):
                yield val.obj


def _paths_from_list_modifications(module_path, trailer1, trailer2):
    """ extract the path from either "sys.path.append" or "sys.path.insert" """
    # Guarantee that both are trailers, the first one a name and the second one
    # a function execution with at least one param.
    if not (pr.is_node(trailer1, 'trailer') and trailer1.children[0] == '.'
            and pr.is_node(trailer2, 'trailer') and trailer2.children[0] == '('
            and len(trailer2.children) == 3):
        return []

    name = trailer1.children[1].value
    if name not in ['insert', 'append']:
        return []

    arg = trailer2.children[1]
    if name == 'insert' and len(arg.children) in (3, 4):  # Possible trailing comma.
        arg = arg.children[2]
    return _execute_code(module_path, arg.get_code())


def _check_module(evaluator, module):
    def get_sys_path_powers(names):
        for power in [p.parent.parent for p in names]:
            if pr.is_node(power, 'power'):
                c = power.children
                if isinstance(c[0], pr.Name) and c[0].value == 'sys' \
                        and pr.is_node(c[1], 'trailer'):
                    n = c[1].children[1]
                    if isinstance(n, pr.Name) and n.value == 'path':
                        yield power

    sys_path = list(get_sys_path())  # copy
    try:
        possible_names = module.used_names['path']
    except KeyError:
        pass
    else:
        for power in get_sys_path_powers(possible_names):
            if len(power.children) >= 4:
                sys_path.extend(_paths_from_list_modifications(module.path, *power.children[2:4]))
            elif hasattr(power, 'assignment_details') \
                    and len(stmt.assignment_details) == 1:
                sys_path.extend(_paths_from_assignment(evaluator, stmt))
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

    result = _check_module(evaluator, module)
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
