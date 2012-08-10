import copy

import parsing
import debug
import builtin


class RecursionDecorator(object):
    """ A decorator to detect recursions in statements """
    def __init__(self, func):
        self.func = func
        self.reset()
        self.current = None

    def __call__(self, stmt, *args, **kwargs):
        r = RecursionNode(stmt, self.current)

        # Don't check param instances, they are not causing recursions
        # The same's true for the builtins, because the builtins are really
        # simple.
        if isinstance(stmt, parsing.Param) or r.script == builtin.Builtin.scope:
            return self.func(stmt, *args, **kwargs)

        if self.check_recursion(r):
            debug.warning('catched recursion', stmt, args, kwargs)
            return []
        parent, self.current = self.current, r
        result = self.func(stmt, *args, **kwargs)
        self.current = parent
        return result

    def check_recursion(self, new):
        test = self.current
        while True:
            if new == test:
                return True
            if not test:
                return False
            test = test.parent

    def reset(self):
        self.top = None
        self.current = None

class RecursionNode(object):
    def __init__(self, stmt, parent):
        self.script = stmt.get_parent_until()
        self.position = stmt.start_pos
        self.parent = parent

    def __eq__(self, other):
        if not other:
            return None
        return self.script == other.script and self.position == other.position


def fast_parent_copy(obj):
    """
    Much, much faster than deepcopy, but just for the elements in `classes`.
    """
    new_elements = {}
    classes = (parsing.Call, parsing.Scope)
    def recursion(obj):
        new_obj = copy.copy(obj)
        new_elements[obj] = new_obj
        try:
            new_obj.parent = new_elements[obj.parent]
        except KeyError:
            pass

        #print new_obj.__dict__
        for key, value in new_obj.__dict__.items():
            if isinstance(value, list):
                new_obj.__dict__[key] = list_rec(value)
        return new_obj

    def list_rec(list_obj):
        copied_list = list_obj[:]   # lists, tuples, strings, unicode
        for i, el in enumerate(copied_list):
            if isinstance(el, classes):
                copied_list[i] = recursion(el)
            elif isinstance(el, list):
                copied_list[i] = list_rec(el)
        return copied_list
    return recursion(obj)

def generate_param_array(args_tuple, parent_stmt=None):
    """ This generates an array, that can be used as a param """
    values = []
    for arg in args_tuple:
        if arg is None:
            values.append([])
        else:
            values.append([arg])
    return parsing.Array(parsing.Array.TUPLE, parent_stmt, values=values)
