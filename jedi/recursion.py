"""
Recursions are the recipe of |jedi| to conquer Python code. However, someone
must stop recursions going mad. Some settings are here to make |jedi| stop at
the right time. You can read more about them :ref:`here <settings-recursion>`.

Next to :mod:`cache` this module also makes |jedi| not thread-safe. Why?
``ExecutionRecursionDecorator`` uses class variables to count the function
calls.
"""
from jedi import parsing_representation as pr
from jedi import debug
from jedi import settings
import evaluate_representation as er
import builtin


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
        check = self._check_recursion()
        if check:  # TODO remove False!!!!
            debug.warning('catched stmt recursion: %s against %s @%s'
                                % (stmt, check.stmt, stmt.start_pos))
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
                return test
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
        self.is_ignored = isinstance(stmt, pr.Param) \
                                   or (self.script == builtin.Builtin.scope)

    def __eq__(self, other):
        if not other:
            return None

        is_list_comp = lambda x: isinstance(x, pr.ForFlow) and x.is_list_comp
        return self.script == other.script \
                    and self.position == other.position \
                    and not is_list_comp(self.stmt.parent) \
                    and not is_list_comp(other.parent) \
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

        if isinstance(execution.base, (er.Generator, er.Array)):
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
