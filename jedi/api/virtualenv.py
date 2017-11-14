import os
import re
import sys
import sysconfig
from subprocess import CalledProcessError
from collections import namedtuple

from jedi._compatibility import check_output
from jedi.evaluate.project import Project
from jedi.cache import memoize_method
from jedi.evaluate.compiled.subprocess import get_subprocess

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

    def get_subprocess(self):
        return get_subprocess(self._executable)

    @memoize_method
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

        return self.get_subprocess().get_sys_path()


class DefaultEnvironment(Environment):
    def __init__(self, script_path):
        # TODO make this usable
        path = script_path
        super(DefaultEnvironment, self).__init__(path, sys.executable)


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
        output = check_output([executable, '--version'])
    except (CalledProcessError, OSError):
        raise NoVirtualEnv()

    match = re.match(rb'Python (\d+)\.(\d+)\.(\d+)', output)
    if match is None:
        raise NoVirtualEnv()

    return _VersionInfo(*match.groups())
