import copy
from itertools import chain
from contextlib import contextmanager

from jedi.parser import tree


def deep_ast_copy(obj):
    """
    Much, much faster than copy.deepcopy, but just for parser tree nodes.
    """
    # If it's already in the cache, just return it.
    new_obj = copy.copy(obj)

    # Copy children
    new_children = []
    for child in obj.children:
        if isinstance(child, tree.Leaf):
            new_child = copy.copy(child)
            new_child.parent = new_obj
        else:
            new_child = deep_ast_copy(child)
            new_child.parent = new_obj
        new_children.append(new_child)
    new_obj.children = new_children

    return new_obj


def evaluate_call_of_leaf(context, leaf, cut_own_trailer=False):
    """
    Creates a "call" node that consist of all ``trailer`` and ``power``
    objects.  E.g. if you call it with ``append``::

        list([]).append(3) or None

    You would get a node with the content ``list([]).append`` back.

    This generates a copy of the original ast node.

    If you're using the leaf, e.g. the bracket `)` it will return ``list([])``.

    # TODO remove cut_own_trailer option, since its always used with it. Just
    #      ignore it, It's not what we want anyway. Or document it better?
    """
    trailer = leaf.parent
    # The leaf may not be the last or first child, because there exist three
    # different trailers: `( x )`, `[ x ]` and `.x`. In the first two examples
    # we should not match anything more than x.
    if trailer.type != 'trailer' or leaf not in (trailer.children[0], trailer.children[-1]):
        if trailer.type == 'atom':
            return context.eval_node(trailer)
        return context.eval_node(leaf)

    power = trailer.parent
    index = power.children.index(trailer)
    if cut_own_trailer:
        cut = index
    else:
        cut = index + 1

    if power.type == 'error_node':
        start = index
        while True:
            start -= 1
            base = power.children[start]
            if base.type != 'trailer':
                break
        trailers = power.children[start + 1: index + 1]
    else:
        base = power.children[0]
        trailers = power.children[1:cut]

    values = context.eval_node(base)
    for trailer in trailers:
        values = context.eval_trailer(values, trailer)
    return values


def call_of_leaf(leaf):
    """
    Creates a "call" node that consist of all ``trailer`` and ``power``
    objects.  E.g. if you call it with ``append``::

        list([]).append(3) or None

    You would get a node with the content ``list([]).append`` back.

    This generates a copy of the original ast node.

    If you're using the leaf, e.g. the bracket `)` it will return ``list([])``.
    """
    # TODO this is the old version of this call. Try to remove it.
    trailer = leaf.parent
    # The leaf may not be the last or first child, because there exist three
    # different trailers: `( x )`, `[ x ]` and `.x`. In the first two examples
    # we should not match anything more than x.
    if trailer.type != 'trailer' or leaf not in (trailer.children[0], trailer.children[-1]):
        if trailer.type == 'atom':
            return trailer
        return leaf

    power = trailer.parent
    index = power.children.index(trailer)

    new_power = copy.copy(power)
    new_power.children = list(new_power.children)
    new_power.children[index + 1:] = []

    if power.type == 'error_node':
        start = index
        while True:
            start -= 1
            if power.children[start].type != 'trailer':
                break
        transformed = tree.Node('power', power.children[start:])
        transformed.parent = power.parent
        return transformed

    return power


def get_names_of_node(node):
    try:
        children = node.children
    except AttributeError:
        if node.type == 'name':
            return [node]
        else:
            return []
    else:
        return list(chain.from_iterable(get_names_of_node(c) for c in children))


def get_module_names(module, all_scopes):
    """
    Returns a dictionary with name parts as keys and their call paths as
    values.
    """
    names = chain.from_iterable(module.used_names.values())
    if not all_scopes:
        # We have to filter all the names that don't have the module as a
        # parent_scope. There's None as a parent, because nodes in the module
        # node have the parent module and not suite as all the others.
        # Therefore it's important to catch that case.
        names = [n for n in names if n.get_parent_scope().parent in (module, None)]
    return names


class FakeName(tree.Name):
    def __init__(self, name_str, parent=None, start_pos=(0, 0), is_definition=None):
        """
        In case is_definition is defined (not None), that bool value will be
        returned.
        """
        super(FakeName, self).__init__(name_str, start_pos)
        self.parent = parent
        self._is_definition = is_definition

    def get_definition(self):
        return self.parent

    def is_definition(self):
        if self._is_definition is None:
            return super(FakeName, self).is_definition()
        else:
            return self._is_definition


@contextmanager
def predefine_names(context, flow_scope, dct):
    predefined = context.predefined_names
    if flow_scope in predefined:
        raise NotImplementedError('Why does this happen?')
    predefined[flow_scope] = dct
    try:
        yield
    finally:
        del predefined[flow_scope]
