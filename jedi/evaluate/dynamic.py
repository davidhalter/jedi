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

from jedi.parser import tree
from jedi import settings
from jedi import debug
from jedi.evaluate.cache import memoize_default
from jedi.evaluate import imports
from jedi.evaluate.param import TreeArguments, create_default_param
from jedi.common import to_list, unite


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
        module_context = parent_context.get_root_context()
        function_executions = _search_function_executions(
            evaluator,
            module_context,
            funcdef
        )
        if function_executions:
            zipped_params = zip(*list(
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
def _search_function_executions(evaluator, module_context, funcdef):
    """
    Returns a list of param names.
    """
    from jedi.evaluate import representation as er

    func_string_name = funcdef.name.value
    compare_node = funcdef
    if func_string_name == '__init__':
        cls = funcdef.get_parent_scope()
        if isinstance(cls, tree.Class):
            func_string_name = cls.name.value
            compare_node = cls

    found_executions = False
    i = 0
    for for_mod_context in imports.get_modules_containing_name(
            evaluator, [module_context], func_string_name):
        if not isinstance(module_context, er.ModuleContext):
            return
        for name, trailer in _get_possible_nodes(for_mod_context, func_string_name):
            i += 1

            # This is a simple way to stop Jedi's dynamic param recursion
            # from going wild: The deeper Jedi's in the recursion, the less
            # code should be evaluated.
            if i * evaluator.dynamic_params_depth > MAX_PARAM_SEARCHES:
                return

            random_context = evaluator.create_context(for_mod_context, name)
            for function_execution in _check_name_for_execution(
                    evaluator, random_context, compare_node, name, trailer):
                found_executions = True
                yield function_execution

        # If there are results after processing a module, we're probably
        # good to process. This is a speed optimization.
        if found_executions:
            return


def _get_possible_nodes(module_context, func_string_name):
    try:
        names = module_context.tree_node.used_names[func_string_name]
    except KeyError:
        return

    for name in names:
        bracket = name.get_next_leaf()
        trailer = bracket.parent
        if trailer.type == 'trailer' and bracket == '(':
            yield name, trailer


def _check_name_for_execution(evaluator, context, compare_node, name, trailer):
    from jedi.evaluate import representation as er, instance

    def create_func_excs():
        arglist = trailer.children[1]
        if arglist == ')':
            arglist = ()
        args = TreeArguments(evaluator, context, arglist, trailer)
        if value_node.type == 'funcdef':
            yield value.get_function_execution(args)
        else:
            created_instance = instance.TreeInstance(
                evaluator,
                value.parent_context,
                value,
                args
            )
            for execution in created_instance.create_init_executions():
                yield execution

    for value in evaluator.goto_definitions(context, name):
        value_node = value.tree_node
        if compare_node == value_node:
            for func_execution in create_func_excs():
                yield func_execution
        elif isinstance(value.parent_context, er.FunctionExecutionContext) and \
                compare_node.type == 'funcdef':
            # Here we're trying to find decorators by checking the first
            # parameter. It's not very generic though. Should find a better
            # solution that also applies to nested decorators.
            params = value.parent_context.get_params()
            if len(params) != 1:
                continue
            values = params[0].infer()
            nodes = [v.tree_node for v in values]
            if nodes == [compare_node]:
                # Found a decorator.
                module_context = context.get_root_context()
                execution_context = next(create_func_excs())
                for name, trailer in _get_possible_nodes(module_context, params[0].string_name):
                    if value_node.start_pos < name.start_pos < value_node.end_pos:
                        random_context = evaluator.create_context(execution_context, name)
                        iterator = _check_name_for_execution(
                            evaluator,
                            random_context,
                            compare_node,
                            name,
                            trailer
                        )
                        for function_execution in iterator:
                            yield function_execution
