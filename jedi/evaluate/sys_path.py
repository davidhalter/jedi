import glob
import imp
import os
import re
import sys
from jedi.evaluate.site import addsitedir

from jedi._compatibility import exec_function, unicode
from jedi.evaluate.cache import evaluator_function_cache
from jedi.evaluate.compiled import CompiledObject
from jedi.evaluate.base_context import ContextualizedNode
from jedi import settings
from jedi import debug
from jedi.evaluate.utils import ignored


def get_python_version():
    pyenv_venv = os.getenv('PYENV_VIRTUAL_ENV')
    if pyenv_venv:
        version = re.findall('/(\d.\d.\d+)/', pyenv_venv)[0]
        return _convert_to_python_version(version)

    pyenv_version = os.getenv('PYENV_VERSION')
    if pyenv_version:
        return _convert_to_python_version(pyenv_version)

    return sys.version_info


def _convert_to_python_version(str_version):
    return tuple(int(n) for n in str_version.split('.'))


def get_venv_path(venv):
    """Get sys.path for specified virtual environment."""
    sys_path = _get_venv_path_dirs(venv)
    with ignored(ValueError):
        sys_path.remove('')
    sys_path = _get_sys_path_with_egglinks(sys_path)
    # As of now, get_venv_path_dirs does not scan built-in pythonpath and
    # user-local site-packages, let's approximate them using path from Jedi
    # interpreter.
    return sys_path + sys.path


def _get_sys_path_with_egglinks(sys_path):
    """Find all paths including those referenced by egg-links.

    Egg-link-referenced directories are inserted into path immediately before
    the directory on which their links were found.  Such directories are not
    taken into consideration by normal import mechanism, but they are traversed
    when doing pkg_resources.require.
    """
    result = []
    for p in sys_path:
        # pkg_resources does not define a specific order for egg-link files
        # using os.listdir to enumerate them, we're sorting them to have
        # reproducible tests.
        for egg_link in sorted(glob.glob(os.path.join(p, '*.egg-link'))):
            with open(egg_link) as fd:
                for line in fd:
                    line = line.strip()
                    if line:
                        result.append(os.path.join(p, line))
                        # pkg_resources package only interprets the first
                        # non-empty line in egg-link files.
                        break
        result.append(p)
    return result


def _get_venv_path_dirs(venv):
    """Get sys.path for venv without starting up the interpreter."""
    venv = os.path.abspath(venv)
    sitedir = _get_venv_sitepackages(venv)
    sys_path = []
    addsitedir(sys_path, sitedir)
    return sys_path


def _get_venv_sitepackages(venv):
    if os.name == 'nt':
        return os.path.join(venv, 'lib', 'site-packages')

    python_version = get_python_version()
    return os.path.join(venv, 'lib', 'python%d.%d' % python_version[:2], 'site-packages')


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


def _paths_from_assignment(module_context, expr_stmt):
    """
    Extracts the assigned strings from an assignment that looks as follows::

    >>> sys.path[0:0] = ['module/path', 'another/module/path']

    This function is in general pretty tolerant (and therefore 'buggy').
    However, it's not a big issue usually to add more paths to Jedi's sys_path,
    because it will only affect Jedi in very random situations and by adding
    more paths than necessary, it usually benefits the general user.
    """
    for assignee, operator in zip(expr_stmt.children[::2], expr_stmt.children[1::2]):
        try:
            assert operator in ['=', '+=']
            assert assignee.type in ('power', 'atom_expr') and \
                len(assignee.children) > 1
            c = assignee.children
            assert c[0].type == 'name' and c[0].value == 'sys'
            trailer = c[1]
            assert trailer.children[0] == '.' and trailer.children[1].value == 'path'
            # TODO Essentially we're not checking details on sys.path
            # manipulation. Both assigment of the sys.path and changing/adding
            # parts of the sys.path are the same: They get added to the current
            # sys.path.
            """
            execution = c[2]
            assert execution.children[0] == '['
            subscript = execution.children[1]
            assert subscript.type == 'subscript'
            assert ':' in subscript.children
            """
        except AssertionError:
            continue

        from jedi.evaluate.syntax_tree import is_string
        cn = ContextualizedNode(module_context.create_context(expr_stmt), expr_stmt)
        for lazy_context in cn.infer().iterate(cn):
            for context in lazy_context.infer():
                if is_string(context):
                    yield context.obj


def _paths_from_list_modifications(module_path, trailer1, trailer2):
    """ extract the path from either "sys.path.append" or "sys.path.insert" """
    # Guarantee that both are trailers, the first one a name and the second one
    # a function execution with at least one param.
    if not (trailer1.type == 'trailer' and trailer1.children[0] == '.'
            and trailer2.type == 'trailer' and trailer2.children[0] == '('
            and len(trailer2.children) == 3):
        return []

    name = trailer1.children[1].value
    if name not in ['insert', 'append']:
        return []
    arg = trailer2.children[1]
    if name == 'insert' and len(arg.children) in (3, 4):  # Possible trailing comma.
        arg = arg.children[2]
    return _execute_code(module_path, arg.get_code())


def _check_module(module_context):
    """
    Detect sys.path modifications within module.
    """
    def get_sys_path_powers(names):
        for name in names:
            power = name.parent.parent
            if power.type in ('power', 'atom_expr'):
                c = power.children
                if c[0].type == 'name' and c[0].value == 'sys' \
                        and c[1].type == 'trailer':
                    n = c[1].children[1]
                    if n.type == 'name' and n.value == 'path':
                        yield name, power

    sys_path = list(module_context.evaluator.project.sys_path)  # copy
    if isinstance(module_context, CompiledObject):
        return sys_path

    try:
        possible_names = module_context.tree_node.get_used_names()['path']
    except KeyError:
        pass
    else:
        for name, power in get_sys_path_powers(possible_names):
            expr_stmt = power.parent
            if len(power.children) >= 4:
                sys_path.extend(
                    _paths_from_list_modifications(
                        module_context.py__file__(), *power.children[2:4]
                    )
                )
            elif expr_stmt is not None and expr_stmt.type == 'expr_stmt':
                sys_path.extend(_paths_from_assignment(module_context, expr_stmt))
    return sys_path


@evaluator_function_cache(default=[])
def sys_path_with_modifications(evaluator, module_context):
    path = module_context.py__file__()
    if path is None:
        # Support for modules without a path is bad, therefore return the
        # normal path.
        return evaluator.project.sys_path

    curdir = os.path.abspath(os.curdir)
    #TODO why do we need a chdir?
    with ignored(OSError):
        os.chdir(os.path.dirname(path))

    buildout_script_paths = set()

    result = _check_module(module_context)
    result += _detect_django_path(path)
    for buildout_script_path in _get_buildout_script_paths(path):
        for path in _get_paths_from_buildout_script(evaluator, buildout_script_path):
            buildout_script_paths.add(path)
    # cleanup, back to old directory
    os.chdir(curdir)
    return list(result) + list(buildout_script_paths)


def _get_paths_from_buildout_script(evaluator, buildout_script_path):
    try:
        module_node = evaluator.grammar.parse(
            path=buildout_script_path,
            cache=True,
            cache_path=settings.cache_directory
        )
    except IOError:
        debug.warning('Error trying to read buildout_script: %s', buildout_script_path)
        return

    from jedi.evaluate.context import ModuleContext
    for path in _check_module(ModuleContext(evaluator, module_node, buildout_script_path)):
        yield path


def traverse_parents(path):
    while True:
        new = os.path.dirname(path)
        if new == path:
            return
        path = new
        yield path


def _get_parent_dir_with_file(path, filename):
    for parent in traverse_parents(path):
        if os.path.isfile(os.path.join(parent, filename)):
            return parent
    return None


def _detect_django_path(module_path):
    """ Detects the path of the very well known Django library (if used) """
    result = []

    for parent in traverse_parents(module_path):
        with ignored(IOError):
            with open(parent + os.path.sep + 'manage.py'):
                debug.dbg('Found django path: %s', module_path)
                result.append(parent)
    return result


def _get_buildout_script_paths(module_path):
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
        except (UnicodeDecodeError, IOError) as e:
            # Probably a binary file; permission error or race cond. because file got deleted
            # ignore
            debug.warning(unicode(e))
            continue
    return extra_module_paths


def dotted_path_in_sys_path(sys_path, module_path):
    """
    Returns the dotted path inside a sys.path.
    """
    # First remove the suffix.
    for suffix, _, _ in imp.get_suffixes():
        if module_path.endswith(suffix):
            module_path = module_path[:-len(suffix)]
        break
    else:
        # There should always be a suffix in a valid Python file on the path.
        return None

    if module_path.startswith(os.path.sep):
        # The paths in sys.path most of the times don't end with a slash.
        module_path = module_path[1:]

    for p in sys_path:
        if module_path.startswith(p):
            rest = module_path[len(p):]
            if rest:
                split = rest.split(os.path.sep)
                for string in split:
                    if not string or '.' in string:
                        return None
                return '.'.join(split)

    return None
