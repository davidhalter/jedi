"""
One of the really important features of |jedi| is to have an option to
understand code like this::

    def foo(bar):
        bar. # completion here
    foo(1)

There's no doubt wheter bar is an ``int`` or not, but if there's also a call
like ``foo('str')``, what would happen? Well, we'll just show both. Because
that's what a human would expect.

It works as follows:

- |Jedi| sees a param
- search for function calls named ``foo``
- execute these calls and check the input. This work with a ``ParamListener``.
"""
from itertools import chain

from jedi._compatibility import unicode
from jedi.parser import tree
from jedi import settings
from jedi import debug
from jedi.evaluate.cache import memoize_default
from jedi.evaluate import imports
from jedi.evaluate.param import TreeArguments, create_default_param
from jedi.common import to_list, unite
from jedi.evaluate import context


MAX_PARAM_SEARCHES = 20


class ParamListener(object):
    """
    This listener is used to get the params for a function.
    """
    def __init__(self):
        self.param_possibilities = []

    def execute(self, params):
        self.param_possibilities += params


class MergedExecutedParams(object):
    """
    Simulates being a parameter while actually just being multiple params.
    """
    def __init__(self, executed_params):
        self._executed_params = executed_params

    def infer(self):
        return unite(p.infer() for p in self._executed_params)


@debug.increase_indent
def search_params(evaluator, parent_context, funcdef):
    """
    A dynamic search for param values. If you try to complete a type:

    >>> def func(foo):
    ...     foo
    >>> func(1)
    >>> func("")

    It is not known what the type ``foo`` without analysing the whole code. You
    have to look for all calls to ``func`` to find out what ``foo`` possibly
    is.
    """
    if not settings.dynamic_params:
        return set()

    evaluator.dynamic_params_depth += 1
    try:
        debug.dbg('Dynamic param search in %s.', funcdef.name.value, color='MAGENTA')
        function_executions = _search_function_executions(evaluator, funcdef)
        if function_executions:
            zipped_params = zip(*(
                function_execution.get_params()
                for function_execution in function_executions
            ))
            params = [MergedExecutedParams(executed_params) for executed_params in zipped_params]
            # Evaluate the ExecutedParams to types.
        else:
            params = [create_default_param(parent_context, p) for p in funcdef.params]
        debug.dbg('Dynamic param result finished', color='MAGENTA')
        return params
    finally:
        evaluator.dynamic_params_depth -= 1


@memoize_default([], evaluator_is_first_arg=True)
@to_list
def _search_function_executions(evaluator, funcdef):
    """
    Returns a list of param names.
    """
    from jedi.evaluate import representation as er

    def get_possible_nodes(module_node, func_name):
            try:
                names = module_node.used_names[func_name]
            except KeyError:
                return

            for name in names:
                bracket = name.get_next_leaf()
                trailer = bracket.parent
                if trailer.type == 'trailer' and bracket == '(':
                    yield name, trailer

    current_module_node = funcdef.get_parent_until()
    func_name = unicode(funcdef.name)
    compare_node = funcdef
    if func_name == '__init__':
        raise NotImplementedError
        cls = funcdef.get_parent_scope()
        if isinstance(cls, tree.Class):
            func_name = unicode(cls.name)
            compare_node = cls

    found_executions = False
    i = 0
    for module_node in imports.get_module_nodes_containing_name(
            evaluator, [current_module_node], func_name):
        module_context = er.ModuleContext(evaluator, module_node)
        for name, trailer in get_possible_nodes(module_node, func_name):
            i += 1

            # This is a simple way to stop Jedi's dynamic param recursion
            # from going wild: The deeper Jedi's in the recursion, the less
            # code should be evaluated.
            if i * evaluator.dynamic_params_depth > MAX_PARAM_SEARCHES:
                return

            random_context = evaluator.create_context(module_context, name)
            for value in evaluator.goto_definitions(random_context, name):
                if compare_node == value.funcdef:
                    arglist = trailer.children[1]
                    if arglist == ')':
                        arglist = ()
                    args = TreeArguments(evaluator, random_context, arglist, trailer)
                    yield er.FunctionExecutionContext(
                        evaluator,
                        value.parent_context,
                        value.funcdef,
                        args
                    )
                    found_executions = True

        # If there are results after processing a module, we're probably
        # good to process. This is a speed optimization.
        if found_executions:
            return
