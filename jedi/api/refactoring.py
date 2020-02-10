import difflib

from parso import split_lines


class ChangedFile(object):
    def __init__(self, grammar, path, module_node, node_to_str_map):
        self._grammar = grammar
        self._path = path
        self._module_node = module_node
        self._node_to_str_map = node_to_str_map

    def get_diff(self):
        old_lines = split_lines(self._module_node.get_code(), keepends=True)
        new_lines = split_lines(self.get_code(), keepends=True)
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=self._path,
            tofile=self._path
        )
        # Apparently there's a space at the end of the diff - for whatever
        # reason.
        return ''.join(diff).rstrip(' ')

    def get_code(self):
        return self._grammar.refactor(self._module_node, self._node_to_str_map)

    def apply(self):
        with open(self._path, 'w') as f:
            f.write(self.get_code())

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self._path)


class Refactoring(object):
    def __init__(self, grammar, file_to_node_changes, renames=()):
        self._grammar = grammar
        self._renames = renames
        self._file_to_node_changes = file_to_node_changes

    def get_changed_files(self):
        return [
            ChangedFile(self._grammar, path, next(iter(map_)).get_root_node(), map_)
            for path, map_ in self._file_to_node_changes.items()
        ]

    def get_renames(self):
        """
        Files can be renamed in a refactoring.

        Returns ``Iterable[Tuple[str, str]]``.
        """
        return self._renames

    def get_diff(self):
        return ''.join(f.get_diff() for f in self.get_changed_files())

    def apply(self):
        for old, new in self._renames:
            rename(old, new)

        for f in self.get_changed_files():
            f.apply()
