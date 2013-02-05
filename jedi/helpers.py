import copy

import parsing_representation as pr


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
            try:
                if before == cls.__slots__:
                    continue
                before = cls.__slots__
                items += [(n, getattr(new_obj, n)) for n in before]
            except AttributeError:
                pass

        for key, value in items:
            # replace parent (first try _parent and then parent)
            if key in ['parent', '_parent', '_parent_stmt'] \
                                                    and value is not None:
                if key == 'parent' and '_parent' in items:
                    # parent can be a property
                    continue
                try:
                    setattr(new_obj, key, new_elements[value])
                except KeyError:
                    pass
            elif key in ['parent_stmt', 'parent_function', 'use_as_parent',
                            'module']:
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


def generate_param_array(args_tuple, parent_stmt=None):
    """ This generates an array, that can be used as a param. """
    values = []
    for arg in args_tuple:
        if arg is None:
            values.append([])
        else:
            values.append([arg])
    pos = None
    arr = pr.Array(pos, pr.Array.TUPLE, parent_stmt, values=values)
    return arr


def check_arr_index(arr, pos):
    positions = arr.arr_el_pos
    for index, comma_pos in enumerate(positions):
        if pos < comma_pos:
            return index
    return len(positions)


def array_for_pos(arr, pos):
    if arr.start_pos >= pos \
            or arr.end_pos[0] is not None and pos >= arr.end_pos:
        return None, None

    result = arr
    for sub in arr:
        for s in sub:
            if isinstance(s, pr.Array):
                result = array_for_pos(s, pos)[0] or result
            elif isinstance(s, pr.Call):
                if s.execution:
                    result = array_for_pos(s.execution, pos)[0] or result
                if s.next:
                    result = array_for_pos(s.next, pos)[0] or result

    return result, check_arr_index(result, pos)


def search_function_call(arr, pos):
    """
    Returns the function Call that matches the position before `arr`.
    This is somehow stupid, probably only the name of the function.
    """
    call = None
    stop = False
    for sub in arr.values:
        call = None
        for s in sub:
            if isinstance(s, pr.Array):
                new = search_function_call(s, pos)
                if new[0] is not None:
                    call, index, stop = new
                    if stop:
                        return call, index, stop
            elif isinstance(s, pr.Call):
                start_s = s
                # check parts of calls
                while s is not None:
                    if s.start_pos >= pos:
                        return call, check_arr_index(arr, pos), stop
                    elif s.execution is not None:
                        end = s.execution.end_pos
                        if s.execution.start_pos < pos and \
                                (None in end or pos < end):
                            c, index, stop = search_function_call(
                                            s.execution, pos)
                            if stop:
                                return c, index, stop

                            # call should return without execution and
                            # next
                            reset = c or s
                            if reset.execution.type not in \
                                        [pr.Array.TUPLE, pr.Array.NOARRAY]:
                                return start_s, index, False

                            reset.execution = None
                            reset.next = None
                            return c or start_s, index, True
                    s = s.next

    # The third return is just necessary for recursion inside, because
    # it needs to know when to stop iterating.
    return call, check_arr_index(arr, pos), stop
