"""
This module is here to ensure compatibility of Windows/Linux/MacOS and
different Python versions.
"""
import errno
import sys
import pickle


def cast_path(string):
    """
    Take a bytes or str path and cast it to unicode.

    Apparently it is perfectly fine to pass both byte and unicode objects into
    the sys.path. This probably means that byte paths are normal at other
    places as well.

    Since this just really complicates everything and Python 2.7 will be EOL
    soon anyway, just go with always strings.
    """
    if isinstance(string, bytes):
        return str(string, encoding='UTF-8', errors='replace')
    return str(string)


def pickle_load(file):
    try:
        return pickle.load(file)
    # Python on Windows don't throw EOF errors for pipes. So reraise them with
    # the correct type, which is caught upwards.
    except OSError:
        if sys.platform == 'win32':
            raise EOFError()
        raise


def pickle_dump(data, file, protocol):
    try:
        pickle.dump(data, file, protocol)
        # On Python 3.3 flush throws sometimes an error even though the writing
        # operation should be completed.
        file.flush()
    # Python on Windows don't throw EPIPE errors for pipes. So reraise them with
    # the correct type and error number.
    except OSError:
        if sys.platform == 'win32':
            raise IOError(errno.EPIPE, "Broken pipe")
        raise
