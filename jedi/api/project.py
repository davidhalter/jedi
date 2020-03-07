import os
import errno
import json
import sys

from jedi._compatibility import FileNotFoundError, PermissionError, \
    IsADirectoryError, scandir
from jedi.api.environment import get_cached_default_environment, create_environment
from jedi.api.exceptions import WrongVersion
from jedi.api.completion import search_in_module
from jedi.api.helpers import split_search_string, get_module_names
from jedi._compatibility import force_unicode
from jedi.inference.imports import load_module_from_path, \
    load_namespace_from_path, iter_module_names
from jedi.inference.sys_path import discover_buildout_paths
from jedi.inference.cache import inference_state_as_method_param_cache
from jedi.inference.references import recurse_find_python_folders_and_files, search_in_file_ios
from jedi.inference.value.module import ModuleValue
from jedi.inference import InferenceState
from jedi.file_io import FolderIO, FileIO
from jedi.common.utils import traverse_parents

_CONFIG_FOLDER = '.jedi'
_CONTAINS_POTENTIAL_PROJECT = 'setup.py', '.git', '.hg', 'requirements.txt', 'MANIFEST.in'

_SERIALIZER_VERSION = 1


def _remove_duplicates_from_path(path):
    used = set()
    for p in path:
        if p in used:
            continue
        used.add(p)
        yield p


def _force_unicode_list(lst):
    return list(map(force_unicode, lst))


class Project(object):
    _environment = None

    @staticmethod
    def _get_config_folder_path(base_path):
        return os.path.join(base_path, _CONFIG_FOLDER)

    @staticmethod
    def _get_json_path(base_path):
        return os.path.join(Project._get_config_folder_path(base_path), 'project.json')

    @classmethod
    def load(cls, path):
        """
        :param path: The path of the directory you want to use as a project.
        """
        with open(cls._get_json_path(path)) as f:
            version, data = json.load(f)

        if version == 1:
            return cls(**data)
        else:
            raise WrongVersion(
                "The Jedi version of this project seems newer than what we can handle."
            )

    def __init__(self, path, **kwargs):
        """
        :param path: The base path for this project.
        :param python_path: The Python executable path, typically the path of a
            virtual environment.
        :param load_unsafe_extensions: Loads extensions that are not in the
            sys path and in the local directories. With this option enabled,
            this is potentially unsafe if you clone a git repository and
            analyze it's code, because those compiled extensions will be
            important and therefore have execution privileges.
        :param sys_path: list of str. You can override the sys path if you
            want. By default the ``sys.path.`` is generated from the
            environment (virtualenvs, etc).
        :param added_sys_path: list of str. Adds these paths at the end of the
            sys path.
        :param smart_sys_path: If this is enabled (default), adds paths from
            local directories. Otherwise you will have to rely on your packages
            being properly configured on the ``sys.path``.
        """
        def py2_comp(path, python_path=None, load_unsafe_extensions=False,
                     sys_path=None, added_sys_path=(), smart_sys_path=True):
            self._path = os.path.abspath(path)

            self._python_path = python_path
            self._sys_path = sys_path
            self._smart_sys_path = smart_sys_path
            self._load_unsafe_extensions = load_unsafe_extensions
            self._django = False
            self.added_sys_path = list(added_sys_path)
            """The sys path that is going to be added at the end of the """

        py2_comp(path, **kwargs)

    @inference_state_as_method_param_cache()
    def _get_base_sys_path(self, inference_state):
        # The sys path has not been set explicitly.
        sys_path = list(inference_state.environment.get_sys_path())
        try:
            sys_path.remove('')
        except ValueError:
            pass
        return sys_path

    @inference_state_as_method_param_cache()
    def _get_sys_path(self, inference_state, add_parent_paths=True, add_init_paths=False):
        """
        Keep this method private for all users of jedi. However internally this
        one is used like a public method.
        """
        suffixed = list(self.added_sys_path)
        prefixed = []

        if self._sys_path is None:
            sys_path = list(self._get_base_sys_path(inference_state))
        else:
            sys_path = list(self._sys_path)

        if self._smart_sys_path:
            prefixed.append(self._path)

            if inference_state.script_path is not None:
                suffixed += discover_buildout_paths(inference_state, inference_state.script_path)

                if add_parent_paths:
                    # Collect directories in upward search by:
                    #   1. Skipping directories with __init__.py
                    #   2. Stopping immediately when above self._path
                    traversed = []
                    for parent_path in traverse_parents(inference_state.script_path):
                        if parent_path == self._path or not parent_path.startswith(self._path):
                            break
                        if not add_init_paths \
                                and os.path.isfile(os.path.join(parent_path, "__init__.py")):
                            continue
                        traversed.append(parent_path)

                    # AFAIK some libraries have imports like `foo.foo.bar`, which
                    # leads to the conclusion to by default prefer longer paths
                    # rather than shorter ones by default.
                    suffixed += reversed(traversed)

        if self._django:
            prefixed.append(self._path)

        path = prefixed + sys_path + suffixed
        return list(_force_unicode_list(_remove_duplicates_from_path(path)))

    def save(self):
        data = dict(self.__dict__)
        data.pop('_environment', None)
        data.pop('_django', None)  # TODO make django setting public?
        data = {k.lstrip('_'): v for k, v in data.items()}

        # TODO when dropping Python 2 use pathlib.Path.mkdir(parents=True, exist_ok=True)
        try:
            os.makedirs(self._get_config_folder_path(self._path))
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        with open(self._get_json_path(self._path), 'w') as f:
            return json.dump((_SERIALIZER_VERSION, data), f)

    def get_environment(self):
        if self._environment is None:
            if self._python_path is not None:
                self._environment = create_environment(self._python_path, safe=False)
            else:
                self._environment = get_cached_default_environment()
        return self._environment

    def search(self, string, complete=False, all_scopes=False):
        """
        Returns a generator of names
        """
        # Using a Script is they easiest way to get an empty module context.
        from jedi import Script
        s = Script('', project=self)
        inference_state = s._inference_state
        empty_module_context = s._get_module_context()

        if inference_state.grammar.version_info < (3, 6) or sys.version_info < (3, 6):
            raise NotImplementedError(
                "No support for refactorings/search on Python 2/3.5"
            )
        wanted_type, wanted_names = split_search_string(string)
        name = wanted_names[0]

        ios = recurse_find_python_folders_and_files(FolderIO(self._path))
        file_ios = []

        # 1. Search for modules in the current project
        for folder_io, file_io in ios:
            if file_io is None:
                file_name = folder_io.get_base_name()
                if file_name == name:
                    f = folder_io.get_file_io('__init__.py')
                    try:
                        m = load_module_from_path(inference_state, f).as_context()
                    except FileNotFoundError:
                        f = folder_io.get_file_io('__init__.pyi')
                        try:
                            m = load_module_from_path(inference_state, f).as_context()
                        except FileNotFoundError:
                            m = load_namespace_from_path(inference_state, folder_io).as_context()
                else:
                    continue
            else:
                file_ios.append(file_io)
                file_name = os.path.basename(file_io.path)
                if file_name in (name + '.py', name + 'pyi'):
                    m = load_module_from_path(inference_state, file_io).as_context()
                else:
                    continue

            for x in search_in_module(
                inference_state,
                m,
                names=[m.name],
                wanted_type=wanted_type,
                wanted_names=wanted_names,
                complete=complete
            ):
                yield x  # Python 2...

        # 2. Search for identifiers in the project.
        for module_context in search_in_file_ios(inference_state, file_ios, name):
            names = get_module_names(module_context.tree_node, all_scopes=all_scopes)
            for x in search_in_module(
                inference_state,
                module_context,
                names=[module_context.create_name(n) for n in names],
                wanted_type=wanted_type,
                wanted_names=wanted_names,
                complete=complete,
                ignore_imports=True,
            ):
                yield x  # Python 2...

        # 3. Search for modules on sys.path
        sys_path = [
            p for p in self._get_sys_path(inference_state)
            # Exclude folders that are handled by recursing of the Python
            # folders.
            if not p.startswith(self._path)
        ]

        names = list(iter_module_names(inference_state, empty_module_context, sys_path))
        for x in search_in_module(
            inference_state,
            empty_module_context,
            names=names,
            wanted_type=wanted_type,
            wanted_names=wanted_names,
            complete=complete
        ):
            yield x  # Python 2...

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self._path)


def _is_potential_project(path):
    for name in _CONTAINS_POTENTIAL_PROJECT:
        if os.path.exists(os.path.join(path, name)):
            return True
    return False


def _is_django_path(directory):
    """ Detects the path of the very well known Django library (if used) """
    try:
        with open(os.path.join(directory, 'manage.py'), 'rb') as f:
            return b"DJANGO_SETTINGS_MODULE" in f.read()
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        return False

    return False


def get_default_project(path=None):
    if path is None:
        path = os.getcwd()

    check = os.path.realpath(path)
    probable_path = None
    first_no_init_file = None
    for dir in traverse_parents(check, include_current=True):
        try:
            return Project.load(dir)
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            pass

        if first_no_init_file is None:
            if os.path.exists(os.path.join(dir, '__init__.py')):
                # In the case that a __init__.py exists, it's in 99% just a
                # Python package and the project sits at least one level above.
                continue
            else:
                first_no_init_file = dir

        if _is_django_path(dir):
            project = Project(dir)
            project._django = True
            return project

        if probable_path is None and _is_potential_project(dir):
            probable_path = dir

    if probable_path is not None:
        # TODO search for setup.py etc
        return Project(probable_path)

    if first_no_init_file is not None:
        return Project(first_no_init_file)

    curdir = path if os.path.isdir(path) else os.path.dirname(path)
    return Project(curdir)


def _get_sys_path_folder_and_file_ios(sys_path):
    for p in sys_path:
        for dir_entry in scandir(p):
            if dir_entry.is_dir():
                yield FolderIO(p), None
            else:
                yield None, FileIO(p)
