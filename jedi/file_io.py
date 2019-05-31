import os

from parso import file_io


class _ListDirMixin(object):
    def listdir(self):
        directory = self.path
        return os.listdir(directory)


class ZipFileIO(file_io.KnownContentFileIO):
    """For .zip and .egg archives"""
    def __init__(self, path, code, zip_path):
        super(ZipFileIO, self).__init__(path, code)
        self._zip_path = zip_path

    def get_last_modified(self):
        try:
            return os.path.getmtime(self._zip_path)
        except OSError:  # Python 3 would probably only need FileNotFoundError
            return None

    def listdir(self):
        return []


class FileIO(_ListDirMixin, file_io.FileIO):
    pass


class KnownContentFileIO(file_io.KnownContentFileIO):
    pass
