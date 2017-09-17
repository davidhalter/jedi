"""
Recursions are the recipe of |jedi| to conquer Python code. However, someone
must stop recursions going mad. Some settings are here to make |jedi| stop at
the right time. You can read more about them :ref:`here <settings-recursion>`.

Next to :mod:`jedi.evaluate.cache` this module also makes |jedi| not
thread-safe. Why?  ``execution_recursion_decorator`` uses class variables to
count the function calls.

.. _settings-recursion:

Settings
~~~~~~~~~~

Recursion settings are important if you don't want extremly
recursive python code to go absolutely crazy. First of there is a
global limit :data:`max_executions`. This limit is important, to set
a maximum amount of time, the completion may use.

The default values are based on experiments while completing the |jedi| library
itself (inception!). But I don't think there's any other Python library that
uses recursion in a similarly extreme way. These settings make the completion
definitely worse in some cases. But a completion should also be fast.

.. autodata:: max_until_execution_unique
.. autodata:: max_function_recursion_level
.. autodata:: max_executions_without_builtins
.. autodata:: max_executions
"""

from contextlib import contextmanager

from jedi import debug


max_until_execution_unique = 50
"""
This limit is probably the most important one, because if this limit is
exceeded, functions can only be one time executed. So new functions will be
executed, complex recursions with the same functions again and again, are
ignored.
"""

max_function_recursion_level = 5
"""
`max_function_recursion_level` is more about whether the recursions are
stopped in deepth or in width. The ratio beetween this and
`max_until_execution_unique` is important here. It stops a recursion (after
the number of function calls in the recursion), if it was already used
earlier.
"""

max_executions_without_builtins = 200
"""
.. todo:: Document this.
"""

max_executions = 250
"""
A maximum amount of time, the completion may use.
"""


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

    def pop_execution(self):
        self.parent_execution_funcs.pop()
        self.recursion_level -= 1

    def push_execution(self, execution):
        self.recursion_level += 1
        self.execution_count += 1
        self.execution_funcs.add(execution.tree_node)
        self.parent_execution_funcs.append(execution.tree_node)

        if self.execution_count > max_executions:
            debug.warning('Too many executions %s' % execution)
            return True

        module = execution.get_root_context()
        if module == self._evaluator.BUILTINS:
            # We have control over builtins so we know they are not recursing
            # like crazy. Therefore we just let them execute always, because
            # they usually just help a lot with getting good results.
            return False

        if execution.tree_node in self.parent_execution_funcs:
            if self.recursion_level > max_function_recursion_level:
                return True
        if execution.tree_node in self.execution_funcs and \
                len(self.execution_funcs) > max_until_execution_unique:
            return True
        if self.execution_count > max_executions_without_builtins:
            return True
        return False
