import os
from contextlib import contextmanager


def traverse_parents(path, root=None, include_current=False):
    """Iterate directories from a path to search root

    :path: the path of the script/directory to check.
    :root: the root of the upward search. Assumes the system root if root is
            None.
    :include_current: includes the current file / directory.

    If the root path is not a substring of the provided path, assume the root
    search path as well.
    """
    if not include_current:
        path = os.path.dirname(path)

    previous = None
    if root is None or not path.startswith(root):
        while previous != path:
            yield path
            previous = path
            path = os.path.dirname(path)
    else:
        while previous != root:
            yield path
            previous = path
            path = os.path.dirname(path)


@contextmanager
def monkeypatch(obj, attribute_name, new_value):
    """
    Like pytest's monkeypatch, but as a value manager.
    """
    old_value = getattr(obj, attribute_name)
    try:
        setattr(obj, attribute_name, new_value)
        yield
    finally:
        setattr(obj, attribute_name, old_value)
