"""
For dynamic completion.

Sorry to everyone who is reading this code. Especially the array parts are
really cryptic and not understandable. It's just a hack, that turned out to be
working quite good.
"""

import parsing
import evaluate
import helpers
import settings
import debug

# This is something like the sys.path, but only for searching params. It means
# that this is the order in which Jedi searches params.
search_param_modules = ['.']
search_param_cache = {}


def search_param_memoize(func):
    """
    Is only good for search params memoize, respectively the closure,
    because it just caches the input, not the func, like normal memoize does.
    """
    def wrapper(*args, **kwargs):
        key = (args, frozenset(kwargs.items()))
        if key in search_param_cache:
            return search_param_cache[key]
        else:
            rv = func(*args, **kwargs)
            search_param_cache[key] = rv
            return rv
    return wrapper


class ParamListener(object):
    """
    This listener is used to get the params for a function.
    """
    def __init__(self):
        self.param_possibilities = []

    def execute(self, params):
        self.param_possibilities.append(params)


def search_params(param):
    """
    This is a dynamic search for params. If you try to complete a type:
    >>> def func(foo):
    >>>     # here is the completion
    >>>     foo
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
        @search_param_memoize
        def get_posibilities(module, func_name):
            try:
                possible_stmts = module.used_names[func_name]
            except KeyError:
                return []

            for stmt in possible_stmts:
                evaluate.follow_statement(stmt)
            return listener.param_possibilities

        result = []
        for params in get_posibilities(module, func_name):
            for p in params:
                if str(p) == param_name:
                    result += evaluate.follow_statement(p.parent())
        #print listener.param_possibilities, param, result

        return result

    func = param.get_parent_until(parsing.Function)
    current_module = param.get_parent_until()
    func_name = str(func.name)
    if func_name == '__init__' and isinstance(func.parent(), parsing.Class):
        func_name = str(func.parent().name)

    # get the param name
    if param.assignment_details:
        arr = param.assignment_details[0][1]
    else:
        arr = param.get_assignment_calls()
    offset = 1 if arr[0][0] in ['*', '**'] else 0
    param_name = str(arr[0][offset].name)

    # add the listener
    listener = ParamListener()
    func.listeners.add(listener)

    result = get_params_for_module(current_module)

    # TODO check other modules
    # cleanup: remove the listener; important: should not stick.
    func.listeners.remove(listener)

    return result

def check_array_additions(array):
    """ Just a mapper function for the internal _check_array_additions """
    if array._array.type not in ['list', 'tuple']:
        # TODO also check for dict updates
        return []

    is_list = array._array.type == 'list'
    current_module = array._array.parent_stmt().get_parent_until()
    res = _check_array_additions(array, current_module, is_list)
    return res


@evaluate.memoize_default([])
def _check_array_additions(compare_array, module, is_list):
    """
    Checks if a `parsing.Array` has "add" statements:
    >>> a = [""]
    >>> a.append(1)
    """
    if not settings.dynamic_array_additions:
        return []

    def scan_array(arr, search_name):
        """ Returns the function Calls that match func_name """
        result = []
        for sub in arr:
            for s in sub:
                if isinstance(s, parsing.Array):
                    result += scan_array(s, search_name)
                elif isinstance(s, parsing.Call):
                    n = s.name
                    if isinstance(n, parsing.Name) and search_name in n.names:
                        result.append(s)
        return result

    def check_calls(calls, add_name):
        result = []
        for c in calls:
            call_path = list(c.generate_call_path())
            separate_index = call_path.index(add_name)
            if not len(call_path) > separate_index + 1:
                # this means that there is no execution -> [].append
                continue
            backtrack_path = iter(call_path[:separate_index])

            position = c.parent_stmt().start_pos
            scope = c.parent_stmt().parent()

            # Special assignments should not be evaluated in this case. This
            # would cause big recursion problems, because in cases like the
            # code of jedi itself, += something is called and this call leads
            # to many other things including params, which are not defined.
            # This would lead again to dynamic param completion, and so on.
            # In the end the definition is needed, and that's not with `+=`.
            settings.evaluate_special_assignments = False
            found = evaluate.follow_call_path(backtrack_path, scope, position)
            settings.evaluate_special_assignments = True
            if not compare_array in found:
                # Check if the original scope is an execution. If it is, one
                # can search for the same statement, that is in the module
                # dict. Executions are somewhat special in jedi, since they
                # literally copy the contents of a function.
                if isinstance(comp_arr_parent, evaluate.Execution):
                    found_bases = []
                    for f in found:
                        base = get_execution_parent(f, parsing.Function)
                        found_bases.append(base)
                    if comp_arr_parent.base.base_func in found_bases:
                        stmt = comp_arr_parent. \
                                        get_statement_for_position(c.start_pos)
                        if stmt is not None:
                            if evaluate.follow_statement.push_stmt(stmt):
                                # check recursion
                                continue
                            ass = stmt.get_assignment_calls()
                            new_calls = scan_array(ass, add_name)
                            #print [c.start_pos for c in new_calls], stmt.start_pos
                            result += check_calls(new_calls, add_name)
                            evaluate.follow_statement.pop_stmt()
                continue

            params = call_path[separate_index + 1]
            if not params.values:
                continue  # no params: just ignore it
            if add_name in ['append', 'add']:
                result += evaluate.follow_call_list(params)
            elif add_name in ['insert']:
                try:
                    second_param = params[1]
                except IndexError:
                    continue
                else:
                    result += evaluate.follow_call_list([second_param])
            elif add_name in ['extend', 'update']:
                iterators = evaluate.follow_call_list(params)
                result += evaluate.get_iterator_types(iterators)
        return result

    def get_execution_parent(element, *stop_classes):
        if isinstance(element, evaluate.Array):
            stmt = element._array.parent_stmt()
        else:
            # must be instance
            stmt = element.var_args.parent_stmt()
        return stmt.get_parent_until(*stop_classes)

    search_names = ['append', 'extend', 'insert'] if is_list else \
                                                            ['add', 'update']
    comp_arr_parent = get_execution_parent(compare_array, evaluate.Execution)
    possible_stmts = []
    result = []
    for n in search_names:
        try:
            possible_stmts += module.used_names[n]
        except KeyError:
            continue
        for stmt in possible_stmts:
            ass = stmt.get_assignment_calls()
            result += check_calls(scan_array(ass, n), n)

    return result


def check_array_instances(instance):
    if not settings.dynamic_arrays_instances:
        return instance.var_args
    ai = ArrayInstance(instance)
    return helpers.generate_param_array([ai], instance.var_args.parent_stmt())


class ArrayInstance(parsing.Base):
    """
    Used for the usage of set() and list().
    This is definitely a hack, but a good one :-)
    It makes it possible to use set/list conversions.
    """
    def __init__(self, instance):
        self.instance = instance
        self.var_args = instance.var_args

    def iter_content(self):
        """
        The index is here just ignored, because of all the appends, etc.
        lists/sets are too complicated too handle that.
        """
        items = []
        for array in evaluate.follow_call_list(self.var_args):
            if isinstance(array, evaluate.Instance) and len(array.var_args):
                temp = array.var_args[0][0]
                if isinstance(temp, ArrayInstance):
                    # prevent recursions
                    # TODO compare Modules
                    if self.var_args.start_pos != temp.var_args.start_pos:
                        items += temp.iter_content()
                    else:
                        debug.warning('ArrayInstance recursion', self.var_args)
                    continue
            items += evaluate.get_iterator_types([array])

        module = self.var_args.parent_stmt().get_parent_until()
        is_list = str(self.instance.name) == 'list'
        items += _check_array_additions(self.instance, module, is_list)
        return items
