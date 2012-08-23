import copy
import weakref

import parsing
import evaluate
import debug
import builtin


class RecursionDecorator(object):
    """ A decorator to detect recursions in statements """
    def __init__(self, func):
        self.func = func
        self.reset()
        self.current = None

    def __call__(self, stmt, *args, **kwargs):
        if self.push_stmt(stmt):
            return []
        else:
            result = self.func(stmt, *args, **kwargs)
            self.pop_stmt()
        return result

    def push_stmt(self, stmt):
        self.current = RecursionNode(stmt, self.current)
        if self._check_recursion():
            debug.warning('catched recursion', stmt)
            self.pop_stmt()
            return True
        return False

    def pop_stmt(self):
        self.current = self.current.parent

    def _check_recursion(self):
        test = self.current
        while True:
            test = test.parent
            if self.current == test:
                return True
            if not test:
                return False

    def reset(self):
        self.top = None
        self.current = None

    def node_statements(self):
        result = []
        n = self.current
        while n:
            result.append(n.stmt)
            n = n.parent
        return result


class RecursionNode(object):
    def __init__(self, stmt, parent):
        self.script = stmt.get_parent_until()
        self.position = stmt.start_pos
        self.parent = parent
        self.stmt = stmt

        # Don't check param instances, they are not causing recursions
        # The same's true for the builtins, because the builtins are really
        # simple.
        self.is_ignored = isinstance(stmt, parsing.Param) \
                                   or (self.script == builtin.Builtin.scope)

    def __eq__(self, other):
        if not other:
            return None
        return self.script == other.script \
                    and self.position == other.position and not self.is_ignored


def fast_parent_copy_old(obj):
    """
    Much, much faster than deepcopy, but just for the elements in `classes`.
    """
    new_elements = {}
    classes = (parsing.Call, parsing.Scope)

    def recursion(obj):
        new_obj = copy.copy(obj)
        new_elements[obj] = new_obj
        if obj.parent is not None:
            try:
                new_obj.parent = weakref.ref(new_elements[obj.parent()])
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

def fast_parent_copy(obj):
    """
    Much, much faster than deepcopy, but just for the elements in `classes`.
    """
    new_elements = {}
    classes = (parsing.Simple, parsing.Call)

    def recursion(obj):
        new_obj = copy.copy(obj)
        new_elements[obj] = new_obj
        if obj.parent is not None:
            try:
                new_obj.parent = weakref.ref(new_elements[obj.parent()])
            except KeyError:
                pass

        #print new_obj.__dict__
        for key, value in new_obj.__dict__.items():
            #if key in ['_parent_stmt', 'parent_stmt', '_parent', 'parent']: print key, value
            if key in ['parent', '_parent']:
                continue
            if isinstance(value, list):
                new_obj.__dict__[key] = list_rec(value)
            elif isinstance(value, classes):
                new_obj.__dict__[key] = recursion(value)
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
fast_parent_copy2 = fast_parent_copy

def generate_param_array(args_tuple, parent_stmt=None):
    """ This generates an array, that can be used as a param """
    values = []
    for arg in args_tuple:
        if arg is None:
            values.append([])
        else:
            values.append([arg])
    pos = None
    arr = parsing.Array(pos, parsing.Array.TUPLE, parent_stmt, values=values)
    evaluate.faked_scopes.append(arr)
    return arr
