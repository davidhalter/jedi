import copy
import weakref

from _compatibility import hasattr
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
            result.append(n.stmt)
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
                                   or (self.script == builtin.builtin_scope)

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

        if isinstance(execution.base, (evaluate.Generator, evaluate.Array)):
            return False
        module = execution.get_parent_until()
        if evaluate_generator or module == builtin.builtin_scope:
            return False

        if in_par_execution_funcs:
            if cls.recursion_level > settings.max_function_recursion_level:
                return True
        if in_execution_funcs and \
                len(cls.execution_funcs) > settings.max_until_execution_unique:
            return True
        if cls.execution_count > settings.max_executions:
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

        for key, value in new_obj.__dict__.items():
            if key in ['parent', '_parent', '_parent_stmt', 'parent_stmt']:
                continue
            if isinstance(value, list):
                new_obj.__dict__[key] = list_rec(value)
            elif isinstance(value, parsing.Simple):
                new_obj.__dict__[key] = recursion(value)

        if obj.parent is not None:
            try:
                new_obj.parent = weakref.ref(new_elements[obj.parent()])
            except KeyError:
                pass

        if hasattr(obj, 'parent_stmt') and obj.parent_stmt is not None:
            p = obj.parent_stmt()
            try:
                new_obj.parent_stmt = weakref.ref(new_elements[p])
            except KeyError:
                pass

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
    evaluate.faked_scopes.append(arr)
    return arr
