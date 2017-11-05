import os
import re
import sysconfig
from subprocess import CalledProcessError
from collections import namedtuple

from jedi._compatibility import check_output
from jedi.evaluate.project import Project
from jedi.cache import memoize_method


_VersionInfo = namedtuple('VersionInfo', 'major minor micro')


class NoVirtualEnv(Exception):
    pass


class Environment(object):
    def __init__(self, path, executable):
        self._path = path
        self._executable = executable
        self.version_info = _get_version(self._executable)

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self._path)

    def get_project(self):
        return Project(self.get_sys_path())

    def get_sys_path(self):
        vars = {
            'base': self._path
        }
        lib_path = sysconfig.get_path('stdlib', vars=vars)
        # It's pretty much impossible to generate the sys path without actually
        # executing Python. The sys path (when starting with -S) itself depends
        # on how the Python version was compiled (ENV variables).
        # If you omit -S when starting Python (normal case), additionally
        # site.py gets executed.
        write

        # venv
        ['', '/usr/lib/python3.3', '/usr/lib/python3.3/plat-x86_64-linux-gnu',
         '/usr/lib/python3.3/lib-dynload',
         '/home/dave/source/python/virtenv/venv3.3/lib/python3.3/site-packages']

        ['/usr/lib/python3.4', '/usr/lib/python3.4/plat-x86_64-linux-gnu',
         '/usr/lib/python3.4/lib-dynload',
         '/home/dave/source/stuff_cloudscale/rgw-metrics/venv/lib/python3.4/site-packages']

        ['', '/usr/lib/python35.zip', '/usr/lib/python3.5',
         '/usr/lib/python3.5/plat-x86_64-linux-gnu',
         '/usr/lib/python3.5/lib-dynload',
         '/home/dave/source/python/virtenv/venv3.5/lib/python3.5/site-packages']


        {'purelib': '{base}/local/lib/python{py_version_short}/dist-packages',
         'stdlib': '{base}/lib/python{py_version_short}',
         'scripts': '{base}/local/bin',
         'platinclude': '{platbase}/local/include/python{py_version_short}',
         'include': '{base}/local/include/python{py_version_short}',
         'data': '{base}/local',
         'platstdlib': '{platbase}/lib/python{py_version_short}',
         'platlib': '{platbase}/local/lib/python{py_version_short}/dist-packages'}
        return [] + additional_paths

    def _get_long_running_process(self):
        return process


def find_virtualenvs(paths=None):
    if paths is None:
        paths = []

    for path in paths:
        executable = _get_executable_path(path)
        try:
            yield Environment(path, executable)
        except NoVirtualEnv:
            pass


def _get_executable_path(path):
    """
    Returns None if it's not actually a virtual env.
    """
    bin_folder = os.path.join(path, 'bin')
    activate = os.path.join(bin_folder, 'activate')
    python = os.path.join(bin_folder, 'python')
    if not all(os.path.exists(p) for p in (activate, python)):
        return None
    return python


def _get_version(executable):
    try:
        output = check_output(executable, '--version')
    except (CalledProcessError, OSError):
        raise NoVirtualEnv()

    match = re.match(r'Python (\d+)\.(\d+)\.(\d+)', output)
    if match is None:
        raise NoVirtualEnv()

    return _VersionInfo(*match.groups())
