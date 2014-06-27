import copy

from jedi import common
from jedi.parser import representation as pr
from jedi import debug


def fast_parent_copy(obj):
    """
    Much, much faster than copy.deepcopy, but just for certain elements.
    """
    new_elements = {}

    def recursion(obj):
        if isinstance(obj, pr.Statement):
            # Need to set _set_vars, otherwise the cache is not working
            # correctly, don't know why.
            obj.get_defined_names()

        new_obj = copy.copy(obj)
        new_elements[obj] = new_obj

        try:
            items = list(new_obj.__dict__.items())
        except AttributeError:
            # __dict__ not available, because of __slots__
            items = []

        before = ()
        for cls in new_obj.__class__.__mro__:
            with common.ignored(AttributeError):
                if before == cls.__slots__:
                    continue
                before = cls.__slots__
                items += [(n, getattr(new_obj, n)) for n in before]

        for key, value in items:
            # replace parent (first try _parent and then parent)
            if key in ['parent', '_parent'] and value is not None:
                if key == 'parent' and '_parent' in items:
                    # parent can be a property
                    continue
                with common.ignored(KeyError):
                    setattr(new_obj, key, new_elements[value])
            elif key in ['parent_function', 'use_as_parent', '_sub_module']:
                continue
            elif isinstance(value, list):
                setattr(new_obj, key, list_rec(value))
            elif isinstance(value, pr.Simple):
                setattr(new_obj, key, recursion(value))
        return new_obj

    def list_rec(list_obj):
        copied_list = list_obj[:]   # lists, tuples, strings, unicode
        for i, el in enumerate(copied_list):
            if isinstance(el, pr.Simple):
                copied_list[i] = recursion(el)
            elif isinstance(el, list):
                copied_list[i] = list_rec(el)
        return copied_list
    return recursion(obj)


def call_signature_array_for_pos(stmt, pos):
    """
    Searches for the array and position of a tuple.
    """
    def search_array(arr, pos):
        accepted_types = pr.Array.TUPLE, pr.Array.NOARRAY
        if arr.type == 'dict':
            for stmt in arr.values + arr.keys:
                new_arr, index = call_signature_array_for_pos(stmt, pos)
                if new_arr is not None:
                    return new_arr, index
        else:
            for i, stmt in enumerate(arr):
                new_arr, index = call_signature_array_for_pos(stmt, pos)
                if new_arr is not None:
                    return new_arr, index

                if arr.start_pos < pos <= stmt.end_pos:
                    if arr.type in accepted_types and isinstance(arr.parent, pr.Call):
                        return arr, i
        if len(arr) == 0 and arr.start_pos < pos < arr.end_pos:
            if arr.type in accepted_types and isinstance(arr.parent, pr.Call):
                return arr, 0
        return None, 0

    def search_call(call, pos):
        arr, index = None, 0
        if call.next is not None:
            if isinstance(call.next, pr.Array):
                arr, index = search_array(call.next, pos)
            else:
                arr, index = search_call(call.next, pos)
        if not arr and call.execution is not None:
            arr, index = search_array(call.execution, pos)
        return arr, index

    if stmt.start_pos >= pos >= stmt.end_pos:
        return None, 0

    for command in stmt.expression_list():
        arr = None
        if isinstance(command, pr.Array):
            arr, index = search_array(command, pos)
        elif isinstance(command, pr.StatementElement):
            arr, index = search_call(command, pos)
        if arr is not None:
            return arr, index
    return None, 0


def search_call_signatures(user_stmt, position):
    """
    Returns the function Call that matches the position before.
    """
    debug.speed('func_call start')
    call, index = None, 0
    if user_stmt is not None and isinstance(user_stmt, pr.Statement):
        # some parts will of the statement will be removed
        user_stmt = fast_parent_copy(user_stmt)
        arr, index = call_signature_array_for_pos(user_stmt, position)
        if arr is not None:
            call = arr.parent

    debug.speed('func_call parsed')
    return call, index


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
                n = s_new.name
                if isinstance(n, pr.Name) \
                        and search_name in [str(x) for x in n.names]:
                    result.append(c)

                if s_new.execution is not None:
                    result += scan_array(s_new.execution, search_name)
                s_new = s_new.next
        elif isinstance(c, pr.ListComprehension):
            for s in c.stmt, c.middle, c.input:
                result += scan_statement_for_calls(s, search_name)

    return result


class FakeSubModule():
    line_offset = 0


class FakeArray(pr.Array):
    def __init__(self, values, parent=None, arr_type=pr.Array.LIST):
        p = (0, 0)
        super(FakeArray, self).__init__(FakeSubModule, p, arr_type, parent)
        self.values = values


class FakeStatement(pr.Statement):
    def __init__(self, expression_list, start_pos=(0, 0), parent=None):
        p = start_pos
        super(FakeStatement, self).__init__(FakeSubModule, expression_list, p, p)
        self.set_expression_list(expression_list)
        self.parent = parent


class FakeImport(pr.Import):
    def __init__(self, name, parent, level=0):
        p = 0, 0
        super(FakeImport, self).__init__(FakeSubModule, p, p, name,
                                         relative_count=level)
        self.parent = parent


class FakeName(pr.Name):
    def __init__(self, name_or_names, parent=None):
        p = 0, 0
        if isinstance(name_or_names, list):
            names = [(n, p) for n in name_or_names]
        else:
            names = [(name_or_names, p)]
        super(FakeName, self).__init__(FakeSubModule, names, p, p, parent)


def stmts_to_stmt(statements):
    """
    Sometimes we want to have something like a result_set and unite some
    statements in one.
    """
    if len(statements) == 1:
        return statements[0]
    array = FakeArray(statements, arr_type=pr.Array.NOARRAY)
    return FakeStatement([array])
