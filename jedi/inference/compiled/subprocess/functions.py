import sys
import os
import inspect
import importlib
import warnings
from pathlib import Path
from zipfile import ZipFile
from zipimport import zipimporter, ZipImportError
from io import FileIO
from typing import (
    Any,
    Optional,
    Sequence,
    Tuple,
    TYPE_CHECKING,
    Union,
)

from jedi.inference.compiled import access
from jedi import debug
from jedi import parser_utils
from jedi.file_io import KnownContentFileIO, ZipFileIO


if TYPE_CHECKING:
    from jedi.inference import InferenceState


ModuleInfoResult = Tuple[Union[Any, FileIO, None], Optional[bool]]


def get_sys_path():
    return sys.path


def load_module(inference_state, **kwargs):
    return access.load_module(inference_state, **kwargs)


def get_compiled_method_return(inference_state, id, attribute, *args, **kwargs):
    handle = inference_state.compiled_subprocess.get_access_handle(id)
    return getattr(handle.access, attribute)(*args, **kwargs)


def create_simple_object(inference_state, obj):
    return access.create_access_path(inference_state, obj)


def get_module_info(
    inference_state: "InferenceState",
    *,
    string: str,
    sys_path: Sequence[str] = None,
    full_name: str = None,
    path: Sequence[str] = None,
    is_global_search: bool = True,
) -> ModuleInfoResult:
    """
    Returns Tuple[Union[NamespaceInfo, FileIO, None], Optional[bool]]
    """
    del inference_state

    if sys_path is not None:
        sys.path, temp = list(sys_path), sys.path
    try:
        return _find_module(
            string=string,
            full_name=full_name,
            path=path,
            is_global_search=is_global_search,
        )
    except ImportError:
        return None, None
    finally:
        if sys_path is not None:
            sys.path = temp


def get_builtin_module_names(inference_state):
    return sys.builtin_module_names


def _test_raise_error(inference_state, exception_type):
    """
    Raise an error to simulate certain problems for unit tests.
    """
    raise exception_type


def _test_print(inference_state, stderr=None, stdout=None):
    """
    Force some prints in the subprocesses. This exists for unit tests.
    """
    if stderr is not None:
        print(stderr, file=sys.stderr)
        sys.stderr.flush()
    if stdout is not None:
        print(stdout)
        sys.stdout.flush()


def safe_literal_eval(inference_state, value):
    return parser_utils.safe_literal_eval(value)


def iter_module_names(*args, **kwargs):
    return list(_iter_module_names(*args, **kwargs))


def _iter_module_names(inference_state, paths):
    # Python modules/packages
    for path in paths:
        try:
            dir_entries = ((entry.name, entry.is_dir()) for entry in os.scandir(path))
        except OSError:
            try:
                zip_import_info = zipimporter(path)
                # Unfortunately, there is no public way to access zipimporter's
                # private _files member. We therefore have to use a
                # custom function to iterate over the files.
                dir_entries = _zip_list_subdirectory(
                    zip_import_info.archive, zip_import_info.prefix)
            except ZipImportError:
                # The file might not exist or reading it might lead to an error.
                debug.warning("Not possible to list directory: %s", path)
                continue
        for name, is_dir in dir_entries:
            # First Namespaces then modules/stubs
            if is_dir:
                # pycache is obviously not an interesting namespace. Also the
                # name must be a valid identifier.
                if name != '__pycache__' and name.isidentifier():
                    yield name
            else:
                if name.endswith('.pyi'):  # Stub files
                    modname = name[:-4]
                else:
                    modname = inspect.getmodulename(name)

                if modname and '.' not in modname:
                    if modname != '__init__':
                        yield modname


def _find_module(
    string: str,
    path: Sequence[str] = None,
    full_name: str = None,
    is_global_search: bool = True,
) -> ModuleInfoResult:
    """
    Provides information about a module.

    This function isolates the differences in importing libraries introduced with
    python 3.3 on; it gets a module name and optionally a path. It will return a
    tuple containin an open file for the module (if not builtin), the filename
    or the name of the module if it is a builtin one and a boolean indicating
    if the module is contained in a package.
    """
    spec = None
    loader = None

    for finder in sys.meta_path:
        if is_global_search and finder != importlib.machinery.PathFinder:  # type: ignore
            p = None
        else:
            p = path

        try:
            find_spec = finder.find_spec
        except AttributeError:
            # These are old-school clases that still have a different API, just
            # ignore those.
            continue

        spec = find_spec(string, p)
        if spec is not None:
            loader = spec.loader
            if loader is None and not spec.has_location:
                # This is a namespace package.
                full_name = string if not path else full_name
                implicit_ns_info = ImplicitNSInfo(
                    full_name,
                    spec.submodule_search_locations._path,  # type: ignore
                )
                return implicit_ns_info, True

            break

    return _find_module_py33(string, path, loader)


def _find_module_py33(
    string: str,
    path: Sequence[str] = None,
    loader: Any = None,
) -> ModuleInfoResult:
    loader = loader or importlib.machinery.PathFinder.find_module(string, path)

    if loader is None and path is None:  # Fallback to find builtins
        try:
            with warnings.catch_warnings(record=True):
                # Mute "DeprecationWarning: Use importlib.util.find_spec()
                # instead." While we should replace that in the future, it's
                # probably good to wait until we deprecate Python 3.3, since
                # it was added in Python 3.4 and find_loader hasn't been
                # removed in 3.6.
                loader = importlib.find_loader(string)
        except ValueError as e:
            # See #491. Importlib might raise a ValueError, to avoid this, we
            # just raise an ImportError to fix the issue.
            raise ImportError("Originally  " + repr(e))

    if loader is None:
        raise ImportError("Couldn't find a loader for {}".format(string))

    return _from_loader(loader, string)


def _from_loader(loader: Any, string: str) -> ModuleInfoResult:
    try:
        is_package_method = loader.is_package
    except AttributeError:
        is_package = False
    else:
        is_package = is_package_method(string)
    try:
        get_filename = loader.get_filename
    except AttributeError:
        return None, is_package
    else:
        module_path = get_filename(string)

    # To avoid unicode and read bytes, "overwrite" loader.get_source if
    # possible.
    try:
        f = type(loader).get_source
    except AttributeError:
        raise ImportError("get_source was not defined on loader")

    if f is not importlib.machinery.SourceFileLoader.get_source:
        # Unfortunately we are reading unicode here, not bytes.
        # It seems hard to get bytes, because the zip importer
        # logic just unpacks the zip file and returns a file descriptor
        # that we cannot as easily access. Therefore we just read it as
        # a string in the cases where get_source was overwritten.
        code = loader.get_source(string)
    else:
        code = _get_source(loader, string)

    if code is None:
        return None, is_package
    if isinstance(loader, zipimporter):
        return ZipFileIO(module_path, code, Path(loader.archive)), is_package

    return KnownContentFileIO(module_path, code), is_package


def _get_source(loader, fullname):
    """
    This method is here as a replacement for SourceLoader.get_source. That
    method returns unicode, but we prefer bytes.
    """
    path = loader.get_filename(fullname)
    try:
        return loader.get_data(path)
    except OSError:
        raise ImportError('source not available through get_data()',
                          name=fullname)


def _zip_list_subdirectory(zip_path, zip_subdir_path):
    zip_file = ZipFile(zip_path)
    zip_subdir_path = Path(zip_subdir_path)
    zip_content_file_paths = zip_file.namelist()
    for raw_file_name in zip_content_file_paths:
        file_path = Path(raw_file_name)
        if file_path.parent == zip_subdir_path:
            file_path = file_path.relative_to(zip_subdir_path)
            yield file_path.name, raw_file_name.endswith("/")


class ImplicitNSInfo:
    """Stores information returned from an implicit namespace spec"""
    def __init__(self, name, paths):
        self.name = name
        self.paths = paths
