from os.path import dirname, basename, join
import os
import re
import difflib

from parso import split_lines

from jedi.api.exceptions import RefactoringError
from jedi.common.utils import indent_block

_EXPRESSION_PARTS = (
    'or_test and_test not_test comparison'
    'xor_expr and_expr shift_expr arith_expr term factor power atom_expr '
).split()
_EXTRACT_USE_PARENT = _EXPRESSION_PARTS + ['trailer']
_DEFINITION_SCOPES = ('suite', 'file_input')
_NON_EXCTRACABLE = ('param',)


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
            funcdef='function',
            classdef='class',
        ).get(expr_stmt.type, expr_stmt.type)
        raise RefactoringError("Cannot inline a %s" % type_)

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
        tree_name = name.tree_name
        path = name.get_root_context().py__file__()
        s = replace_code
        if rhs.type == 'testlist_star_expr' \
                or tree_name.parent.type in _EXPRESSION_PARTS \
                or tree_name.parent.type == 'trailer' \
                and tree_name.parent.get_next_sibling() is not None:
            s = '(' + replace_code + ')'

        of_path = file_to_node_changes.setdefault(path, {})

        n = tree_name
        prefix = n.prefix
        par = n.parent
        if par.type == 'trailer' and par.children[0] == '.':
            prefix = par.parent.children[0].prefix
            n = par
            for some_node in par.parent.children[:par.parent.children.index(par)]:
                of_path[some_node] = ''
        of_path[n] = prefix + s

    path = definitions[0].get_root_context().py__file__()
    changes = file_to_node_changes.setdefault(path, {})
    changes[expr_stmt] = _remove_indent_of_prefix(expr_stmt.get_first_leaf().prefix)
    next_leaf = expr_stmt.get_next_leaf()

    # Most of the time we have to remove the newline at the end of the
    # statement, but if there's a comment we might not need to.
    if next_leaf.prefix.strip(' \t') == '' \
            and (next_leaf.type == 'newline' or next_leaf == ';'):
        changes[next_leaf] = ''
    return Refactoring(grammar, file_to_node_changes)


def extract_variable(grammar, path, module_node, new_name, pos, until_pos):
    start_leaf = module_node.get_leaf_for_position(pos, include_prefixes=True)
    if start_leaf.type == 'operator':
        next_leaf = start_leaf.get_next_leaf()
        if next_leaf is not None and next_leaf.start_pos == pos:
            start_leaf = next_leaf
    if until_pos is None:
        node = start_leaf
        if node.type == 'operator':
            node = node.parent
        while node.parent.type in _EXTRACT_USE_PARENT:
            node = node.parent
        start_leaf
        nodes = [node]
    else:
        end_leaf = module_node.get_leaf_for_position(until_pos, include_prefixes=True)
        if end_leaf.start_pos > until_pos:
            end_leaf = end_leaf.get_previous_leaf()
            if end_leaf is None:
                raise RefactoringError('Cannot extract anything from that')
        parent_node = start_leaf
        while parent_node.end_pos < end_leaf.end_pos:
            parent_node = parent_node.parent

        nodes = _remove_unwanted_expression_nodes(parent_node, pos, until_pos)
    if any(node.type == 'name' and node.is_definition() for node in nodes):
        raise RefactoringError('Cannot extract a definition of a name')
    if any(node.type in _NON_EXCTRACABLE for node in nodes) \
            or nodes[0].type == 'keyword' and nodes[0].value not in ('None', 'True', 'False'):
        raise RefactoringError('Cannot extract a %s' % node.type)

    definition = _get_parent_definition(nodes[0])
    first_definition_leaf = definition.get_first_leaf()

    dct = {}
    extracted = ''.join(n.get_code(include_prefix=i != 0) for i, n in enumerate(nodes))
    extracted_prefix = _insert_line_before(
        first_definition_leaf.prefix,
        new_name + ' = ' + extracted,
    )
    first_node_leaf = nodes[0].get_first_leaf()
    if first_node_leaf is first_definition_leaf:
        dct[nodes[0]] = extracted_prefix + new_name
    else:
        dct[nodes[0]] = first_node_leaf.prefix + new_name
        dct[first_definition_leaf] = extracted_prefix + first_definition_leaf.value

    for node in nodes[1:]:
        dct[node] = ''
    file_to_node_changes = {path: dct}
    return Refactoring(grammar, file_to_node_changes)


def _remove_indent_of_prefix(prefix):
    r"""
    Removes the last indentation of a prefix, e.g. " \n \n " becomes " \n \n".
    """
    return ''.join(split_lines(prefix, keepends=True)[:-1])


def _insert_line_before(prefix, code):
    lines = split_lines(prefix, keepends=True)
    lines[-1:-1] = [indent_block(code, lines[-1]) + '\n']
    return ''.join(lines)


def _get_parent_definition(node):
    """
    Returns the statement where a node is defined.
    """
    while node is not None:
        if node.parent.type in _DEFINITION_SCOPES:
            return node
        node = node.parent
    raise NotImplementedError('We should never even get here')


def _remove_unwanted_expression_nodes(parent_node, pos, until_pos):
    """
    This function makes it so for `1 * 2 + 3` you can extract `2 + 3`, even
    though it is not part of the expression.
    """
    if parent_node.type in _EXPRESSION_PARTS:
        nodes = parent_node.children
        for i, n in enumerate(nodes):
            if n.end_pos > pos:
                start_index = i
                if n.type == 'operator':
                    start_index -= 1
                break
        for i, n in reversed(list(enumerate(nodes))):
            if n.start_pos < until_pos:
                end_index = i
                if n.type == 'operator':
                    end_index += 1
                break
        nodes = nodes[start_index:end_index + 1]
        nodes[0:1] = _remove_unwanted_expression_nodes(nodes[0], pos, until_pos)
        nodes[-1:] = _remove_unwanted_expression_nodes(nodes[-1], pos, until_pos)
        return nodes
    return [parent_node]
