from __future__ import with_statement

import copy

from jedi import common
from jedi import parsing_representation as pr


def fast_parent_copy(obj):
    """
    Much, much faster than copy.deepcopy, but just for certain elements.
    """
    new_elements = {}

    def recursion(obj):
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
            elif isinstance(value, (pr.Simple, pr.Call)):
                setattr(new_obj, key, recursion(value))
        return new_obj

    def list_rec(list_obj):
        copied_list = list_obj[:]   # lists, tuples, strings, unicode
        for i, el in enumerate(copied_list):
            if isinstance(el, (pr.Simple, pr.Call)):
                copied_list[i] = recursion(el)
            elif isinstance(el, list):
                copied_list[i] = list_rec(el)
        return copied_list
    return recursion(obj)


def check_arr_index(arr, pos):
    positions = arr.arr_el_pos
    for index, comma_pos in enumerate(positions):
        if pos < comma_pos:
            return index
    return len(positions)


def array_for_pos(stmt, pos, array_types=None):
    """Searches for the array and position of a tuple"""
    def search_array(arr, pos):
        if arr.type == 'dict':
            for stmt in arr.values + arr.keys:
                new_arr, index = array_for_pos(stmt, pos, array_types)
                if new_arr is not None:
                    return new_arr, index
        else:
            for i, stmt in enumerate(arr):
                new_arr, index = array_for_pos(stmt, pos, array_types)
                if new_arr is not None:
                    return new_arr, index
                if arr.start_pos < pos <= stmt.end_pos:
                    if not array_types or arr.type in array_types:
                        return arr, i
        if len(arr) == 0 and arr.start_pos < pos < arr.end_pos:
            if not array_types or arr.type in array_types:
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

    for command in stmt.get_commands():
        arr = None
        if isinstance(command, pr.Array):
            arr, index = search_array(command, pos)
        elif isinstance(command, pr.Call):
            arr, index = search_call(command, pos)
        if arr is not None:
            return arr, index
    return None, 0


def search_function_definition(stmt, pos):
    """
    Returns the function Call that matches the position before.
    """
    # some parts will of the statement will be removed
    stmt = fast_parent_copy(stmt)
    arr, index = array_for_pos(stmt, pos, [pr.Array.TUPLE, pr.Array.NOARRAY])
    if arr is not None and isinstance(arr.parent, pr.Call):
        call = arr.parent
        while isinstance(call.parent, pr.Call):
            call = call.parent
        arr.parent.execution = None
        return call, index, False
    return None, 0, False
