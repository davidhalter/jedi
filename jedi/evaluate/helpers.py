import copy
from itertools import chain

from jedi._compatibility import unicode
from jedi.parser import tree as pr
from jedi import debug


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

        if isinstance(obj, pr.Statement):
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

        if isinstance(obj, pr.Statement):
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
        except KeyError: # TODO this keyerror is useless.
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


def _call_signature_array_for_pos(stmt, pos):
    """
    Searches for the array and position of a tuple.
    Returns a tuple of (array, index-in-the-array, call).
    """
    def search_array(arr, pos, origin_call=None):
        accepted_types = pr.Array.TUPLE, pr.Array.NOARRAY
        if arr.type == 'dict':
            for stmt in arr.values + arr.keys:
                tup = _call_signature_array_for_pos(stmt, pos)
                if tup[0] is not None:
                    return tup
        else:
            for i, stmt in enumerate(arr):
                tup = _call_signature_array_for_pos(stmt, pos)
                if tup[0] is not None:
                    return tup

                # Since we need the index, we duplicate efforts (with empty
                # arrays).
                if arr.start_pos < pos <= stmt.end_pos:
                    if arr.type in accepted_types and origin_call:
                        return arr, i, origin_call

        if len(arr) == 0 and arr.start_pos < pos < arr.end_pos:
            if arr.type in accepted_types and origin_call:
                return arr, 0, origin_call
        return None, 0, None

    def search_call(call, pos, origin_call=None):
        tup = None, 0, None
        while call.next is not None and tup[0] is None:
            method = search_array if isinstance(call.next, pr.Array) else search_call
            # TODO This is wrong, don't call search_call again, because it will
            # automatically be called by call.next.
            tup = method(call.next, pos, origin_call or call)
            call = call.next
        return tup

    if stmt.start_pos >= pos >= stmt.end_pos:
        return None, 0, None

    tup = None, 0, None
    # TODO this is still old
    for command in [] and stmt.expression_list():
        if isinstance(command, pr.Array):
            tup = search_array(command, pos)
        elif isinstance(command, pr.StatementElement):
            tup = search_call(command, pos, command)
        if tup[0] is not None:
            break
    return tup


def scan_node_for_call_signature(node, pos):
    """to something with call_signatures"""
    if node.type == 'power' and node.start_pos < pos < node.end_pos:
        for i, trailer in enumerate(node.children[1:], 1):
            if trailer.type == 'trailer' and trailer.children[0] == '(' \
                    and trailer.children[0].start_pos < pos \
                    and pos <= trailer.children[-1].start_pos:
                # Delete all the nodes including the current one
                node.children[i:] = []
                return node, trailer
    for child in node.children:
        node, trailer = scan_node_for_call_signature(child, pos)
        if node is not None:
            return node, trailer
    return None, None


def search_call_signatures(user_stmt, position):
    """
    Returns the function Call that matches the position before.
    """
    debug.speed('func_call start')
    call, arr, index = None, None, 0
    if user_stmt is not None and isinstance(user_stmt, pr.ExprStmt):
        # some parts will of the statement will be removed
        user_stmt = deep_ast_copy(user_stmt)

        return scan_node_for_call_signature(user_stmt, position) + (0,)
        #arr, index, call = _call_signature_array_for_pos(user_stmt, position)

        # Now remove the part after the call. Including the array from the
        # statement.
        stmt_el = call
        # TODO REMOVE this? or change?
        while False and isinstance(stmt_el, pr.StatementElement):
            if stmt_el.next == arr:
                stmt_el.next = None
                break
            stmt_el = stmt_el.next

    debug.speed('func_call parsed')
    return call, arr, index


def scan_statement_for_calls(stmt, search_name, assignment_details=False):
    """ Returns the function Calls that match search_name in an Array. """
    def scan_array(arr, search_name):
        result = []
        if arr.type == pr.Array.DICT:
            for key_stmt, value_stmt in arr.items():
                result += scan_statement_for_calls(key_stmt, search_name)
                result += scan_statement_for_calls(value_stmt, search_name)
        else:
            for stmt in arr:
                result += scan_statement_for_calls(stmt, search_name)
        return result

    check = list(stmt.expression_list())
    if assignment_details:
        for expression_list, op in stmt.assignment_details:
            check += expression_list

    result = []
    for c in check:
        if isinstance(c, pr.Array):
            result += scan_array(c, search_name)
        elif isinstance(c, pr.Call):
            s_new = c
            while s_new is not None:
                if isinstance(s_new, pr.Array):
                    result += scan_array(s_new, search_name)
                else:
                    if search_name == unicode(s_new.name):
                        result.append(c)

                s_new = s_new.next
        elif isinstance(c, pr.ListComprehension):
            for s in c.stmt, c.middle, c.input:
                result += scan_statement_for_calls(s, search_name)

    return result


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


def statement_elements_in_statement(stmt):
    """
    Returns a list of statements. Statements can contain statements again in
    Arrays.
    """
    def search_stmt_el(stmt_el, stmt_els):
        stmt_els.append(stmt_el)
        while stmt_el is not None:
            if isinstance(stmt_el, pr.Array):
                for stmt in stmt_el.values + stmt_el.keys:
                    stmt_els.extend(statement_elements_in_statement(stmt))
            stmt_el = stmt_el.next

    stmt_els = []
    for as_name in stmt.as_names:
        # TODO This creates a custom pr.Call, we shouldn't do that.
        stmt_els.append(pr.Call(as_name._sub_module, as_name,
                                as_name.start_pos, as_name.end_pos))

    ass_items = chain.from_iterable(items for items, op in stmt.assignment_details)
    for item in stmt.expression_list() + list(ass_items):
        if isinstance(item, pr.StatementElement):
            search_stmt_el(item, stmt_els)
        elif isinstance(item, pr.ListComprehension):
            for stmt in (item.stmt, item.middle, item.input):
                stmt_els.extend(statement_elements_in_statement(stmt))
        elif isinstance(item, pr.Lambda):
            for stmt in item.params + item.returns:
                stmt_els.extend(statement_elements_in_statement(stmt))

    return stmt_els


class FakeSubModule():
    line_offset = 0
    parent = None
    path = None


class FakeArray(pr.Array):
    def __init__(self, values, parent=None, arr_type=pr.Array.LIST):
        p = (0, 0)
        super(FakeArray, self).__init__(FakeSubModule, p, arr_type, parent)
        self.values = values


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


def stmts_to_stmt(statements):
    """
    Sometimes we want to have something like a result_set and unite some
    statements in one.
    """
    if len(statements) == 1:
        return statements[0]
    array = FakeArray(statements, arr_type=pr.Array.NOARRAY)
    return FakeStatement([array])
