import copy
import contextlib

import parsing
import evaluate
import debug
import builtin
import settings


class RecursionDecorator(object):
    """
    A decorator to detect recursions in statements. In a recursion a statement
    at the same place, in the same module may not be executed two times.
    """
    def __init__(self, func):
        self.func = func
        self.reset()

    def __call__(self, stmt, *args, **kwargs):
        #print stmt, len(self.node_statements())
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
        if self.current is not None:
            # I don't know how current can be None, but sometimes it happens
            # with Python3.
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
            result.insert(0, n.stmt)
            n = n.parent
        return result


class RecursionNode(object):
    """ A node of the RecursionDecorator. """
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
                    and self.position == other.position \
                    and not self.is_ignored and not other.is_ignored


class ExecutionRecursionDecorator(object):
    """
    Catches recursions of executions.
    It is designed like a Singelton. Only one instance should exist.
    """
    def __init__(self, func):
        self.func = func
        self.reset()

    def __call__(self, execution, evaluate_generator=False):
        debug.dbg('Execution recursions: %s' % execution, self.recursion_level,
                            self.execution_count, len(self.execution_funcs))
        if self.check_recursion(execution, evaluate_generator):
            result = []
        else:
            result = self.func(execution, evaluate_generator)
        self.cleanup()
        return result

    @classmethod
    def cleanup(cls):
        cls.parent_execution_funcs.pop()
        cls.recursion_level -= 1

    @classmethod
    def check_recursion(cls, execution, evaluate_generator):
        in_par_execution_funcs = execution.base in cls.parent_execution_funcs
        in_execution_funcs = execution.base in cls.execution_funcs
        cls.recursion_level += 1
        cls.execution_count += 1
        cls.execution_funcs.add(execution.base)
        cls.parent_execution_funcs.append(execution.base)

        if cls.execution_count > settings.max_executions:
            return True

        if isinstance(execution.base, (evaluate.Generator, evaluate.Array)):
            return False
        module = execution.get_parent_until()
        if evaluate_generator or module == builtin.Builtin.scope:
            return False

        if in_par_execution_funcs:
            if cls.recursion_level > settings.max_function_recursion_level:
                return True
        if in_execution_funcs and \
                len(cls.execution_funcs) > settings.max_until_execution_unique:
            return True
        if cls.execution_count > settings.max_executions_without_builtins:
            return True
        return False

    @classmethod
    def reset(cls):
        cls.recursion_level = 0
        cls.parent_execution_funcs = []
        cls.execution_funcs = set()
        cls.execution_count = 0


def fast_parent_copy(obj):
    """
    Much, much faster than copy.deepcopy, but just for certain elements.
    """
    new_elements = {}

    def recursion(obj):
        new_obj = copy.copy(obj)
        new_elements[obj] = new_obj

        items = new_obj.__dict__.items()
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
            elif key in ['parent_stmt', 'parent_function', 'set_parent',
                            'module']:
                continue
            elif isinstance(value, list):
                setattr(new_obj, key, list_rec(value))
            elif isinstance(value, (parsing.Simple, parsing.Call)):
                setattr(new_obj, key, recursion(value))
        return new_obj

    def list_rec(list_obj):
        copied_list = list_obj[:]   # lists, tuples, strings, unicode
        for i, el in enumerate(copied_list):
            if isinstance(el, (parsing.Simple, parsing.Call)):
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
    arr = parsing.Array(pos, parsing.Array.TUPLE, parent_stmt, values=values)
    return arr


def scan_array_for_pos(arr, pos):
    """
    Returns the function Call that match search_name in an Array.
    Makes changes to arr!
    """
    def check_arr_index():
        positions = arr.arr_el_pos
        for index, comma_pos in enumerate(positions):
            if pos < comma_pos:
                return index
        return len(positions)

    call = None
    stop = False
    for sub in arr.values:
        call = None
        for s in sub:
            if isinstance(s, parsing.Array):
                new = scan_array_for_pos(s, pos)
                if new[0] is not None:
                    call, index, stop = new
                    if stop:
                        return call, index, stop
            elif isinstance(s, parsing.Call):
                start_s = s
                # check parts of calls
                while s is not None:
                    if s.start_pos >= pos:
                        return call, check_arr_index(), stop
                    elif s.execution is not None:
                        end = s.execution.end_pos
                        if s.execution.start_pos < pos and \
                                (None in end or pos < end):
                            c, index, stop = scan_array_for_pos(
                                                    s.execution, pos)
                            if stop:
                                return c, index, stop

                            # call should return without execution and
                            # next
                            reset = c or s
                            if reset.execution.type not in \
                                        [parsing.Array.TUPLE,
                                        parsing.Array.NOARRAY]:
                                return start_s, index, False

                            reset.execution = None
                            reset.next = None
                            return c or start_s, index, True
                    s = s.next

    # The third return is just necessary for recursion inside, because
    # it needs to know when to stop iterating.
    return call, check_arr_index(), stop
