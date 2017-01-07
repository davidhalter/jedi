"""
Recursions are the recipe of |jedi| to conquer Python code. However, someone
must stop recursions going mad. Some settings are here to make |jedi| stop at
the right time. You can read more about them :ref:`here <settings-recursion>`.

Next to :mod:`jedi.evaluate.cache` this module also makes |jedi| not
thread-safe. Why?  ``execution_recursion_decorator`` uses class variables to
count the function calls.
"""
from contextlib import contextmanager

from jedi import debug
from jedi import settings


class RecursionDetector(object):
    def __init__(self):
        self.pushed_nodes = []


@contextmanager
def execution_allowed(evaluator, node):
    """
    A decorator to detect recursions in statements. In a recursion a statement
    at the same place, in the same module may not be executed two times.
    """
    pushed_nodes = evaluator.recursion_detector.pushed_nodes

    if node in pushed_nodes:
        debug.warning('catched stmt recursion: %s @%s', node,
                      node.start_pos)
        yield False
    else:
        pushed_nodes.append(node)
        yield True
        pushed_nodes.pop()


def execution_recursion_decorator(default=set()):
    def decorator(func):
        def wrapper(execution, **kwargs):
            detector = execution.evaluator.execution_recursion_detector
            allowed = detector.push_execution(execution)
            try:
                if allowed:
                    result = default
                else:
                    result = func(execution, **kwargs)
            finally:
                detector.pop_execution()
            return result
        return wrapper
    return decorator


class ExecutionRecursionDetector(object):
    """
    Catches recursions of executions.
    """
    def __init__(self, evaluator):
        self.recursion_level = 0
        self.parent_execution_funcs = []
        self.execution_funcs = set()
        self.execution_count = 0
        self._evaluator = evaluator

    def __call__(self, execution):
        debug.dbg('Execution recursions: %s', execution, self.recursion_level,
                  self.execution_count, len(self.execution_funcs))
        if self.check_recursion(execution):
            result = set()
        else:
            result = self.func(execution)
        self.pop_execution()
        return result

    def pop_execution(self):
        self.parent_execution_funcs.pop()
        self.recursion_level -= 1

    def push_execution(self, execution):
        in_par_execution_funcs = execution.tree_node in self.parent_execution_funcs
        in_execution_funcs = execution.tree_node in self.execution_funcs
        self.recursion_level += 1
        self.execution_count += 1
        self.execution_funcs.add(execution.tree_node)
        self.parent_execution_funcs.append(execution.tree_node)

        if self.execution_count > settings.max_executions:
            return True

        module = execution.get_root_context()
        if module == self._evaluator.BUILTINS:
            return False

        if in_par_execution_funcs:
            if self.recursion_level > settings.max_function_recursion_level:
                return True
        if in_execution_funcs and \
                len(self.execution_funcs) > settings.max_until_execution_unique:
            return True
        if self.execution_count > settings.max_executions_without_builtins:
            return True
        return False
