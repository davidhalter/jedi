import sys
import os

from importlib.machinery import FileFinder


class ExactImporter(object):
    def __init__(self, path_dct):
        self._path_dct = path_dct

    def find_module(self, fullname, path=None):
        if path is None and fullname in self._path_dct:
            loader, _ = FileFinder(self._path_dct[fullname]).find_loader(fullname)
            return loader
        return None


def _create_importer():
    # Get the path to jedi.
    _d = os.path.dirname
    _jedi_path = _d(_d(_d(_d(_d(__file__)))))
    _parso_path = sys.argv[1]
    # The paths are the directory that jedi and parso lie in.
    return ExactImporter({'jedi': _jedi_path, 'parso': _parso_path})


# Remove the first entry, because it's simply a directory entry that equals
# this directory.
del sys.path[0]

# Try to import jedi/parso.
sys.meta_path.insert(0, _create_importer())
from jedi.evaluate.compiled import subprocess  # NOQA
sys.meta_path.pop(0)

# And finally start the client.
subprocess.Listener().listen()
