from os.path import dirname, basename, join
import os
import re
import difflib

from parso import split_lines

from jedi.api.exceptions import RefactoringError


class ChangedFile(object):
    def __init__(self, grammar, from_path, to_path, module_node, node_to_str_map):
        self._grammar = grammar
        self._from_path = from_path
        self._to_path = to_path
        self._module_node = module_node
        self._node_to_str_map = node_to_str_map

    def get_diff(self):
        old_lines = split_lines(self._module_node.get_code(), keepends=True)
        new_lines = split_lines(self.get_new_code(), keepends=True)
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=self._from_path,
            tofile=self._to_path
        )
        # Apparently there's a space at the end of the diff - for whatever
        # reason.
        return ''.join(diff).rstrip(' ')

    def get_new_code(self):
        return self._grammar.refactor(self._module_node, self._node_to_str_map)

    def apply(self):
        if self._from_path is None:
            raise RefactoringError(
                'Cannot apply a refactoring on a Script with path=None'
            )

        with open(self._from_path, 'w') as f:
            f.write(self.get_new_code())

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self._from_path)


class Refactoring(object):
    def __init__(self, grammar, file_to_node_changes, renames=()):
        self._grammar = grammar
        self._renames = renames
        self._file_to_node_changes = file_to_node_changes

    def get_changed_files(self):
        """
        Returns a path to ``ChangedFile`` map. The files can be used
        ``Dict[str
        """
        def calculate_to_path(p):
            if p is None:
                return p
            for from_, to in renames:
                if p.startswith(from_):
                    p = to + p[len(from_):]
            return p

        renames = self.get_renames()
        return {
            path: ChangedFile(
                self._grammar,
                from_path=path,
                to_path=calculate_to_path(path),
                module_node=next(iter(map_)).get_root_node(),
                node_to_str_map=map_
            ) for path, map_ in self._file_to_node_changes.items()
        }

    def get_renames(self):
        """
        Files can be renamed in a refactoring.

        Returns ``Iterable[Tuple[str, str]]``.
        """
        return sorted(self._renames, key=lambda x: (-len(x), x))

    def get_diff(self):
        text = ''
        for from_, to in self.get_renames():
            text += 'rename from %s\nrename to %s\n' % (from_, to)

        return text + ''.join(f.get_diff() for f in self.get_changed_files().values())

    def apply(self):
        """
        Applies the whole refactoring to the files, which includes renames.
        """
        for f in self.get_changed_files().values():
            f.apply()

        for old, new in self.get_renames():
            os.rename(old, new)


def _calculate_rename(path, new_name):
    name = basename(path)
    dir_ = dirname(path)
    if name in ('__init__.py', '__init__.pyi'):
        parent_dir = dirname(dir_)
        return dir_, join(parent_dir, new_name)
    ending = re.search(r'\.pyi?$', name).group(0)
    return path, join(dir_, new_name + ending)


def rename(grammar, definitions, new_name):
    file_renames = set()
    file_tree_name_map = {}

    if not definitions:
        raise RefactoringError("There is no name under the cursor")

    for d in definitions:
        tree_name = d._name.tree_name
        if d.type == 'module' and tree_name is None:
            file_renames.add(_calculate_rename(d.module_path, new_name))
        else:
            # This private access is ok in a way. It's not public to
            # protect Jedi users from seeing it.
            if tree_name is not None:
                fmap = file_tree_name_map.setdefault(d.module_path, {})
                fmap[tree_name] = tree_name.prefix + new_name
    return Refactoring(grammar, file_tree_name_map, file_renames)


def inline(grammar, names):
    if not names:
        raise RefactoringError("There is no name under the cursor")
    if any(n.api_type == 'module' for n in names):
        raise RefactoringError("Cannot inline imports or modules")
    if any(n.tree_name is None for n in names):
        raise RefactoringError("Cannot inline builtins/extensions")

    definitions = [n for n in names if n.tree_name.is_definition()]
    if len(definitions) == 0:
        raise RefactoringError("No definition found to inline")
    if len(definitions) > 1:
        raise RefactoringError("Cannot inline a name with multiple definitions")

    tree_name = definitions[0].tree_name

    expr_stmt = tree_name.get_definition()
    if expr_stmt.type != 'expr_stmt':
        type_ = dict(
            funcdef='a function',
            classdef='a class',
        ).get(expr_stmt.type, expr_stmt.type)
        raise RefactoringError("Cannot inline %s" % type_)

    if len(expr_stmt.get_defined_names(include_setitem=True)) > 1:
        raise RefactoringError("Cannot inline a statement with multiple definitions")
    first_child = expr_stmt.children[1]
    if first_child.type == 'annassign' and len(first_child.children) == 4:
        first_child = first_child.children[2]
    if first_child != '=':
        if first_child.type == 'annassign':
            raise RefactoringError(
                'Cannot inline a statement that is defined by an annotation'
            )
        else:
            raise RefactoringError(
                'Cannot inline a statement with "%s"'
                % first_child.get_code(include_prefix=False)
            )

    rhs = expr_stmt.get_rhs()
    replace_code = rhs.get_code(include_prefix=False)

    references = [n for n in names if not n.tree_name.is_definition()]
    file_to_node_changes = {}
    for name in references:
        path = name.get_root_context().py__file__()
        s = replace_code
        if rhs.type == 'testlist_star_expr':
            s = '(' + replace_code + ')'
        file_to_node_changes.setdefault(path, {})[name.tree_name] = \
            name.tree_name.prefix + s

    path = definitions[0].get_root_context().py__file__()
    file_to_node_changes.setdefault(path, {})[expr_stmt] = \
        _remove_indent_and_newline_of_prefix(expr_stmt.get_first_leaf().prefix)
    return Refactoring(grammar, file_to_node_changes)


def _remove_indent_and_newline_of_prefix(prefix):
    r"""
    Removes the last indentation of a prefix, e.g. " \n \n " becomes " \n \n".
    """
    lines = split_lines(prefix, keepends=True)[:-1]
    if lines and lines[-1].endswith('\n'):
        # Remove the newline
        lines[-1] = lines[-1][:-1]
    return ''.join(lines)
