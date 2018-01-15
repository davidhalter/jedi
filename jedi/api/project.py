import os
import json

from jedi._compatibility import FileNotFoundError
from jedi.api.environment import DefaultEnvironment, \
    get_default_environment, from_executable
from jedi.api.exceptions import WrongVersion

_CONFIG_FOLDER = '.jedi'
_CONTAINS_POTENTIAL_PROJECT = 'setup.py', '.git', '.hg', 'MANIFEST.in'

_SERIALIZER_VERSION = 1


class Project(object):
    _serializer_ignore_attributes = ('_environment',)
    _environment = None
    _executable = None

    @staticmethod
    def _get_json_path(base_path):
        return os.path.join(base_path, _CONFIG_FOLDER, 'project.json')

    @classmethod
    def load(cls, path):
        """
        :param path: The path of the directory you want to use as a project.
        """
        with open(cls._get_json_path(path)) as f:
            version, data = json.load(f)

        if version == 1:
            self = cls.__new__()
            self.__dict__.update(data)
            if self._executable is not None:
                self._environment = from_executable(self._executable)
            return self
        else:
            raise WrongVersion(
                "The Jedi version of this project seems newer than what we can handle."
            )

    def __init__(self, path, **kwargs):
        """
        :param path: The base path for this project.
        """
        def py2_comp(path, environment=None, sys_path=None):
            self._path = path
            if isinstance(environment, DefaultEnvironment):
                self._environment = environment
                self._executable = environment._executable

            self._sys_path = sys_path

        py2_comp(path, **kwargs)

    def _get_sys_path(self, environment=None):
        if self._sys_path is not None:
            return self._sys_path

        # The sys path has not been set explicitly.
        if environment is None:
            environment = self.get_environment()

        return environment.get_sys_path()

    def save(self):
        data = dict(self.__dict__)
        for attribute in self._serializer_ignore_attributes:
            data.pop(attribute, None)

        with open(self._get_json_path(self._path), 'wb') as f:
            return json.dump((_SERIALIZER_VERSION, data), f)

    def get_environment(self):
        if self._environment is None:
            return get_default_environment()

        return self._environment

    def __setstate__(self, state):
        self.__dict__.update(state)


def _is_potential_project(path):
    for name in _CONTAINS_POTENTIAL_PROJECT:
        if os.path.exists(os.path.join(path)):
            return True
    return False


def get_default_project():
    previous = None
    curdir = dir = os.path.realpath(os.curdir())
    probable_path = None
    while dir != previous:
        try:
            return Project.load(dir)
        except FileNotFoundError:
            pass

        if probable_path is None and _is_potential_project(dir):
            probable_path = dir

        previous = dir
        dir = os.path.dirname(dir)
    else:
        if probable_path is not None:
            # TODO search for setup.py etc
            return Project(probable_path)
        return Project(curdir)
