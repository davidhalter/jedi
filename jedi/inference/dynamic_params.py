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
- execute these calls and check the input.
"""

from jedi import settings
from jedi import debug
from jedi.inference.cache import inference_state_function_cache
from jedi.inference import imports
from jedi.inference.arguments import TreeArguments
from jedi.inference.param import create_default_params
from jedi.inference.helpers import is_stdlib_path
from jedi.inference.utils import to_list
from jedi.parser_utils import get_parent_scope
from jedi.inference.value import instance
from jedi.inference.base_value import ValueSet, NO_VALUES
from jedi.inference import recursion
from jedi.inference.names import ParamNameWrapper


MAX_PARAM_SEARCHES = 20


class DynamicExecutedParamName(ParamNameWrapper):
    """
    Simulates being a parameter while actually just being multiple params.
    """

    def __init__(self, executed_param_names):
        super(DynamicExecutedParamName, self).__init__(executed_param_names[0])
        self._executed_param_names = executed_param_names

    def infer(self):
        inf = self.parent_context.inference_state
        with recursion.execution_allowed(inf, self) as allowed:
            # We need to catch recursions that may occur, because an
            # anonymous functions can create an anonymous parameter that is
            # more or less self referencing.
            if allowed:
                return ValueSet.from_sets(p.infer() for p in self._executed_param_names)
            return NO_VALUES


@debug.increase_indent
def search_param_names(inference_state, execution_context, funcdef):
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
        return create_default_params(execution_context, funcdef)

    inference_state.dynamic_params_depth += 1
    try:
        path = execution_context.get_root_context().py__file__()
        if path is not None and is_stdlib_path(path):
            # We don't want to search for usages in the stdlib. Usually people
            # don't work with it (except if you are a core maintainer, sorry).
            # This makes everything slower. Just disable it and run the tests,
            # you will see the slowdown, especially in 3.6.
            return create_default_params(execution_context, funcdef)

        if funcdef.type == 'lambdef':
            string_name = _get_lambda_name(funcdef)
            if string_name is None:
                return create_default_params(execution_context, funcdef)
        else:
            string_name = funcdef.name.value
        debug.dbg('Dynamic param search in %s.', string_name, color='MAGENTA')

        try:
            module_context = execution_context.get_root_context()
            function_executions = _search_function_executions(
                inference_state,
                module_context,
                funcdef,
                string_name=string_name,
            )
            if function_executions:
                zipped_param_names = zip(*list(
                    function_execution.get_executed_param_names_and_issues()[0]
                    for function_execution in function_executions
                ))
                params = [DynamicExecutedParamName(executed_param_names)
                          for executed_param_names in zipped_param_names]
            else:
                return create_default_params(execution_context, funcdef)
        finally:
            debug.dbg('Dynamic param result finished', color='MAGENTA')
        return params
    finally:
        inference_state.dynamic_params_depth -= 1


@inference_state_function_cache(default=None)
@to_list
def _search_function_executions(inference_state, module_context, funcdef, string_name):
    """
    Returns a list of param names.
    """
    compare_node = funcdef
    if string_name == '__init__':
        cls = get_parent_scope(funcdef)
        if cls.type == 'classdef':
            string_name = cls.name.value
            compare_node = cls

    found_executions = False
    i = 0
    for for_mod_context in imports.get_module_contexts_containing_name(
            inference_state, [module_context], string_name):
        for name, trailer in _get_potential_nodes(for_mod_context, string_name):
            i += 1

            # This is a simple way to stop Jedi's dynamic param recursion
            # from going wild: The deeper Jedi's in the recursion, the less
            # code should be inferred.
            if i * inference_state.dynamic_params_depth > MAX_PARAM_SEARCHES:
                return

            random_context = for_mod_context.create_context(name)
            for function_execution in _check_name_for_execution(
                    inference_state, random_context, compare_node, name, trailer):
                found_executions = True
                yield function_execution

        # If there are results after processing a module, we're probably
        # good to process. This is a speed optimization.
        if found_executions:
            return


def _get_lambda_name(node):
    stmt = node.parent
    if stmt.type == 'expr_stmt':
        first_operator = next(stmt.yield_operators(), None)
        if first_operator == '=':
            first = stmt.children[0]
            if first.type == 'name':
                return first.value

    return None


def _get_potential_nodes(module_value, func_string_name):
    try:
        names = module_value.tree_node.get_used_names()[func_string_name]
    except KeyError:
        return

    for name in names:
        bracket = name.get_next_leaf()
        trailer = bracket.parent
        if trailer.type == 'trailer' and bracket == '(':
            yield name, trailer


def _check_name_for_execution(inference_state, context, compare_node, name, trailer):
    from jedi.inference.value.function import FunctionExecutionContext

    def create_func_excs(value):
        arglist = trailer.children[1]
        if arglist == ')':
            arglist = None
        args = TreeArguments(inference_state, context, arglist, trailer)
        if value.tree_node.type == 'classdef':
            created_instance = instance.TreeInstance(
                inference_state,
                value.parent_context,
                value,
                args
            )
            for execution in created_instance.create_init_executions():
                yield execution
        else:
            yield value.as_context(args)

    for value in inference_state.goto_definitions(context, name):
        value_node = value.tree_node
        if compare_node == value_node:
            for func_execution in create_func_excs(value):
                yield func_execution
        elif isinstance(value.parent_context, FunctionExecutionContext) and \
                compare_node.type == 'funcdef':
            # Here we're trying to find decorators by checking the first
            # parameter. It's not very generic though. Should find a better
            # solution that also applies to nested decorators.
            param_names, _ = value.parent_context.get_executed_param_names_and_issues()
            if len(param_names) != 1:
                continue
            values = param_names[0].infer()
            nodes = [v.tree_node for v in values]
            if nodes == [compare_node]:
                # Found a decorator.
                module_context = context.get_root_context()
                execution_context = next(create_func_excs(value))
                potential_nodes = _get_potential_nodes(module_context, param_names[0].string_name)
                for name, trailer in potential_nodes:
                    if value_node.start_pos < name.start_pos < value_node.end_pos:
                        random_context = execution_context.create_context(name)
                        iterator = _check_name_for_execution(
                            inference_state,
                            random_context,
                            compare_node,
                            name,
                            trailer
                        )
                        for function_execution in iterator:
                            yield function_execution
