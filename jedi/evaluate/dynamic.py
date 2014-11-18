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

from jedi._compatibility import unicode
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
        return []
    from jedi.evaluate import representation as er

    def get_params_for_module(module):
        """
        Returns the values of a param, or an empty array.
        """
        @memoize_default([], evaluator_is_first_arg=True)
        def get_posibilities(evaluator, module, func_name):
            try:
                names = module.used_names[func_name]
            except KeyError:
                return []

            for name in names:
                stmt = name.get_definition()
                if not isinstance(stmt, (pr.ExprStmt, pr.CompFor)):
                    continue
                parent = name.parent
                if pr.is_node(parent, 'trailer'):
                    parent = parent.parent

                trailer = None
                if pr.is_node(parent, 'power'):
                    for t in parent.children[1:]:
                        if t == '**':
                            break
                        if t.start_pos > name.start_pos and t.children[0] == '(':
                            trailer = t
                            break
                if trailer is not None:
                    types = evaluator.goto_definition(name)

                    # We have to remove decorators, because they are not the
                    # "original" functions, this way we can easily compare.
                    # At the same time we also have to remove InstanceElements.
                    undec = [escope.decorates or
                             (escope.var if isinstance(escope, er.InstanceElement) else escope)
                             for escope in types if escope.isinstance(er.Function, er.Class)]
                    if er.wrap(evaluator, compare) in undec:
                        # Only if we have the correct function we execute
                        # it, otherwise just ignore it.
                        evaluator.eval_trailer(types, trailer)


                # TODO REMOVE
                continue
                calls = helpers.scan_statement_for_calls(stmt, func_name)
                for c in calls:
                    # no execution means that params cannot be set
                    call_path = list(c.generate_call_path())
                    pos = c.start_pos
                    scope = stmt.parent

                    # This whole stuff is just to not execute certain parts
                    # (speed improvement), basically we could just call
                    # ``eval_call_path`` on the call_path and it would also
                    # work.
                    def listRightIndex(lst, value):
                        return len(lst) - lst[-1::-1].index(value) - 1

                    # Need to take right index, because there could be a
                    # func usage before.
                    call_path_simple = [unicode(d) if isinstance(d, pr.Name)
                                        else d for d in call_path]
                    i = listRightIndex(call_path_simple, func_name)
                    before, after = call_path[:i], call_path[i + 1:]
                    if not after and not call_path_simple.index(func_name) != i:
                        continue
                    scopes = [scope]
                    if before:
                        scopes = evaluator.eval_call_path(iter(before), c.parent, pos)
                        pos = None
                    for scope in scopes:
                        # Not resolving decorators is a speed hack:
                        # By ignoring them, we get the function that is
                        # probably called really fast. If it's not called, it
                        # doesn't matter. But this is a way to get potential
                        # candidates for calling that function really quick!
                        s = evaluator.find_types(scope, func_name, position=pos,
                                                 search_global=not before,
                                                 resolve_decorator=False)

                        c = [getattr(escope, 'base_func', None) or escope.base
                             for escope in s
                             if escope.isinstance(er.Function, er.Class)]
                        if compare in c:
                            # only if we have the correct function we execute
                            # it, otherwise just ignore it.
                            evaluator.follow_path(iter(after), s, scope)
            return listener.param_possibilities

        result = []
        for params in get_posibilities(evaluator, module, func_name):
            for p in params:
                if str(p) == str(param.get_name()):
                    result += p.parent.eval(evaluator)
        return result

    func = param.get_parent_until(pr.Function)
    current_module = param.get_parent_until()
    func_name = unicode(func.name)
    compare = func
    if func_name == '__init__':
        cls = func.get_parent_scope()
        if isinstance(cls, pr.Class):
            func_name = unicode(cls.name)
            compare = cls

    # add the listener
    listener = ParamListener()
    func.listeners.add(listener)

    try:
        result = []
        # This is like backtracking: Get the first possible result.
        for mod in imports.get_modules_containing_name([current_module], func_name):
            result = get_params_for_module(mod)
            if result:
                break
    finally:
        # cleanup: remove the listener; important: should not stick.
        func.listeners.remove(listener)

    return result
