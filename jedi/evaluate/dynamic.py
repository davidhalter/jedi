"""
To understand Python on a deeper level, |jedi| needs to understand some of the
dynamic features of Python, however this probably the most complicated part:

- Array modifications (e.g. ``list.append``)
- Parameter completion in functions
- Flow checks (e.g. ``if isinstance(a, str)`` -> a is a str)

Array modifications
*******************

If the content of an array (``set``/``list``) is wanted somewhere, the current
module will be checked for appearances of ``arr.append``, ``arr.insert``, etc.
If the ``arr`` name points to an actual array, the content will be added

This can be really cpu intensive, as you can imagine. Because |jedi| has to
follow **every** ``append``. However this works pretty good, because in *slow*
cases, the recursion detector and other settings will stop this process.

It is important to note that:

1. Array modfications work only in the current module
2. Only Array additions are being checked, ``list.pop``, etc. is being ignored.

Parameter completion
********************

One of the really important features of |jedi| is to have an option to
understand code like this::

    def foo(bar):
        bar. # completion here
    foo(1)

There's no doubt wheter bar is an ``int`` or not, but if there's also a call
like ``foo('str')``, what would happen? Well, we'll just show both. Because
that's what a human would expect.

It works as follows:

- A param is being encountered
- search for function calls named ``foo``
- execute these calls and check the injected params. This work with a
  ``ParamListener``.

Flow checks
***********

Flow checks are not really mature. There's only a check for ``isinstance``.  It
would check whether a flow has the form of ``if isinstance(a, type_or_tuple)``.
Unfortunately every other thing is being ignored (e.g. a == '' would be easy to
check for -> a is a string). There's big potential in these checks.
"""
from jedi.parser import representation as pr
from jedi import settings
from jedi.evaluate import helpers
from jedi.evaluate.cache import memoize_default
from jedi.evaluate import imports

# This is something like the sys.path, but only for searching params. It means
# that this is the order in which Jedi searches params.
search_param_modules = ['.']


class ParamListener(object):
    """
    This listener is used to get the params for a function.
    """
    def __init__(self):
        self.param_possibilities = []

    def execute(self, params):
        self.param_possibilities.append(params)


@memoize_default([], evaluator_is_first_arg=True)
def search_params(evaluator, param):
    """
    This is a dynamic search for params. If you try to complete a type:

    >>> def func(foo):
    ...     foo
    >>> func(1)
    >>> func("")

    It is not known what the type is, because it cannot be guessed with
    recursive madness. Therefore one has to analyse the statements that are
    calling the function, as well as analyzing the incoming params.
    """
    if not settings.dynamic_params:
        return []

    def get_params_for_module(module):
        """
        Returns the values of a param, or an empty array.
        """
        @memoize_default([], evaluator_is_first_arg=True)
        def get_posibilities(evaluator, module, func_name):
            try:
                possible_stmts = module.used_names[func_name]
            except KeyError:
                return []

            for stmt in possible_stmts:
                if isinstance(stmt, pr.Import):
                    continue
                calls = helpers.scan_statement_for_calls(stmt, func_name)
                for c in calls:
                    # no execution means that params cannot be set
                    call_path = list(c.generate_call_path())
                    pos = c.start_pos
                    scope = stmt.parent

                    # this whole stuff is just to not execute certain parts
                    # (speed improvement), basically we could just call
                    # ``eval_call_path`` on the call_path and it would
                    # also work.
                    def listRightIndex(lst, value):
                        return len(lst) - lst[-1::-1].index(value) - 1

                    # Need to take right index, because there could be a
                    # func usage before.
                    i = listRightIndex(call_path, func_name)
                    first, last = call_path[:i], call_path[i + 1:]
                    if not last and not call_path.index(func_name) != i:
                        continue
                    scopes = [scope]
                    if first:
                        scopes = evaluator.eval_call_path(iter(first), scope, pos)
                        pos = None
                    from jedi.evaluate import representation as er
                    for scope in scopes:
                        s = evaluator.find_types(scope, func_name, position=pos,
                                                 search_global=not first,
                                                 resolve_decorator=False)

                        c = [getattr(escope, 'base_func', None) or escope.base
                             for escope in s
                             if escope.isinstance(er.Function, er.Class)]
                        if compare in c:
                            # only if we have the correct function we execute
                            # it, otherwise just ignore it.
                            evaluator.follow_path(iter(last), s, scope)

            return listener.param_possibilities

        result = []
        for params in get_posibilities(evaluator, module, func_name):
            for p in params:
                if str(p) == param_name:
                    result += evaluator.eval_statement(p.parent)
        return result

    func = param.get_parent_until(pr.Function)
    current_module = param.get_parent_until()
    func_name = str(func.name)
    compare = func
    if func_name == '__init__' and isinstance(func.parent, pr.Class):
        func_name = str(func.parent.name)
        compare = func.parent

    # get the param name
    if param.assignment_details:
        # first assignment details, others would be a syntax error
        expression_list, op = param.assignment_details[0]
    else:
        expression_list = param.expression_list()
    offset = 1 if expression_list[0] in ['*', '**'] else 0
    param_name = str(expression_list[offset].name)

    # add the listener
    listener = ParamListener()
    func.listeners.add(listener)

    result = []
    # This is like backtracking: Get the first possible result.
    for mod in imports.get_modules_containing_name([current_module], func_name):
        result = get_params_for_module(mod)
        if result:
            break

    # cleanup: remove the listener; important: should not stick.
    func.listeners.remove(listener)

    return result
