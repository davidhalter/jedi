import copy
from itertools import chain

from jedi.parser import tree as pr


def deep_ast_copy(obj, new_elements_default=None, check_first=False):
    """
    Much, much faster than copy.deepcopy, but just for Parser elements (Doesn't
    copy parents).
    """
    def sort_stmt(key_value):
        return key_value[0] not in ('_expression_list', '_assignment_details')

    new_elements = new_elements_default or {}
    unfinished_parents = []

    def recursion(obj, check_first=False):
        # If it's already in the cache, just return it.
        try:
            new_obj = new_elements[obj]
            if not check_first:
                return new_obj
        except KeyError:
            # Actually copy and set attributes.
            new_obj = copy.copy(obj)
            new_elements[obj] = new_obj

        if isinstance(obj, pr.ExprStmt):
            # Need to set _set_vars, otherwise the cache is not working
            # correctly, don't know exactly why.
            obj.get_defined_names()

        # Gather items
        try:
            items = list(obj.__dict__.items())
        except AttributeError:
            # __dict__ not available, because of __slots__
            items = []

        before = ()
        for cls in obj.__class__.__mro__:
            try:
                if before == cls.__slots__:
                    continue
                before = cls.__slots__
                items += [(n, getattr(obj, n)) for n in before]
            except AttributeError:
                pass

        if isinstance(obj, pr.ExprStmt):
            # We need to process something with priority for statements,
            # because there are several references that don't walk the whole
            # tree in there.
            items = sorted(items, key=sort_stmt)
        else:
            # names_dict should be the last item.
            items = sorted(items, key=lambda x: (x[0] == 'names_dict', x[0] == 'params'))

        #if hasattr(new_obj, 'parent'): print(new_obj, new_obj.parent)

        for key, value in items:
            # replace parent (first try _parent and then parent)
            if key in ['parent', '_parent'] and value is not None:
                if key == 'parent' and '_parent' in items:
                    # parent can be a property
                    continue
                try:
                    if not check_first:
                        setattr(new_obj, key, new_elements[value])
                except KeyError:
                    unfinished_parents.append(new_obj)
            elif key in ['parent_function', 'use_as_parent', '_sub_module']:
                continue
            elif key == 'names_dict':
                d = dict((k, sequence_recursion(v)) for k, v in value.items())
                setattr(new_obj, key, d)
            elif isinstance(value, (list, tuple)):
                setattr(new_obj, key, sequence_recursion(value))
            elif isinstance(value, (pr.Simple, pr.Name)):
                setattr(new_obj, key, recursion(value))

        return new_obj

    def sequence_recursion(array_obj):
        if isinstance(array_obj, tuple):
            copied_array = list(array_obj)
        else:
            copied_array = array_obj[:]   # lists, tuples, strings, unicode
        for i, el in enumerate(copied_array):
            if isinstance(el, (tuple, list)):
                copied_array[i] = sequence_recursion(el)
            else:
                copied_array[i] = recursion(el)

        if isinstance(array_obj, tuple):
            return tuple(copied_array)
        return copied_array

    result = recursion(obj, check_first=check_first)

    # TODO this sucks... we need to change it.
    # DOESNT WORK
    for unfinished in unfinished_parents:
        try:
            unfinished.parent = new_elements[unfinished.parent]
        except KeyError:  # TODO this keyerror is useless.
            pass

    return result


def call_of_name(name, cut_own_trailer=False):
    """
    Creates a "call" node that consist of all ``trailer`` and ``power``
    objects.  E.g. if you call it with ``append``::

        list([]).append(3) or None

    You would get a node with the content ``list([]).append`` back.

    This generates a copy of the original ast node.
    """
    par = name
    if pr.is_node(par.parent, 'trailer'):
        par = par.parent

    power = par.parent
    if pr.is_node(power, 'power') and power.children[0] != name \
            and not (power.children[-2] == '**' and
                     name.start_pos > power.children[-1].start_pos):
        par = power
        # Now the name must be part of a trailer
        index = par.children.index(name.parent)
        if index != len(par.children) - 1 or cut_own_trailer:
            # Now we have to cut the other trailers away.
            par = deep_ast_copy(par)
            if not cut_own_trailer:
                # Normally we would remove just the stuff after the index, but
                # if the option is set remove the index as well. (for goto)
                index = index + 1
            par.children[index:] = []

    return par


def get_module_names(module, all_scopes):
    """
    Returns a dictionary with name parts as keys and their call paths as
    values.
    """
    if all_scopes:
        dct = module.used_names
    else:
        dct = module.names_dict
    return chain.from_iterable(dct.values())


class FakeSubModule():
    line_offset = 0
    parent = None
    path = None


class FakeStatement(pr.ExprStmt):
    def __init__(self, values, start_pos=(0, 0), parent=None):
        self._start_pos = start_pos
        super(FakeStatement, self).__init__([])
        self.values = values
        self.parent = parent

    @property
    def start_pos(self):
        """Overwriting the original start_pos property."""
        return self._start_pos

    def __repr__(self):
        return '<%s: %s>' % (type(self).__name__, self.values)


class FakeImport(pr.Import):
    def __init__(self, name, parent, level=0):
        super(FakeImport, self).__init__([])
        self.parent = parent
        self._level = level
        self.name = name

    def aliases(self):
        return {}

    @property
    def level(self):
        return self._level

    @property
    def start_pos(self):
        return 0, 0

    def paths(self):
        return [[self.name]]


class FakeName(pr.Name):
    def __init__(self, name_str, parent=None, start_pos=(0, 0)):
        super(FakeName, self).__init__(name_str, start_pos)
        self.parent = parent

    def get_definition(self):
        return self.parent


class LazyName(FakeName):
    def __init__(self, name, parent_callback):
        super(LazyName, self).__init__(name)
        self._parent_callback = parent_callback

    @property
    def parent(self):
        return self._parent_callback()

    @parent.setter
    def parent(self, value):
        pass  # Do nothing, super classes can try to set the parent.
