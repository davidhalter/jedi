"""
For dynamic completion.

Sorry to everyone who is reading this code. Especially the array parts are
really cryptic and not understandable. It's just a hack, that turned out to be
working quite good.
"""

import parsing
import evaluate
import helpers

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
    def get_params_for_module(module):
        """
        Returns the values of a param, or an empty array.
        """
        try:
            possible_stmts = current_module.used_names[func_name]
        except KeyError:
            return []

        for stmt in possible_stmts:
            evaluate.follow_statement(stmt)

        result = []
        for params in listener.param_possibilities:
            for p in params:
                if str(p) == param_name:
                    result += evaluate.follow_statement(p.parent)
        #print listener.param_possibilities, param, result

        return result

    func = param.get_parent_until(parsing.Function)
    current_module = param.get_parent_until()
    func_name = str(func.name)
    if func_name == '__init__' and isinstance(func.parent, parsing.Class):
        func_name = str(func.parent.name)

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
    # cleanup: remove the listener
    func.listeners.remove(listener)

    return result


def check_array_additions(array):
    """ Just a mapper function for the internal _check_array_additions """
    is_list = array._array.type == 'list'
    current_module = array._array.parent_stmt.get_parent_until()
    return _check_array_additions(array, current_module, is_list)

@evaluate.memoize_default([])
def _check_array_additions(compare_array, module, is_list):
    """
    Checks if a `parsing.Array` has "add" statements:
    >>> a = [""]
    >>> a.append(1)
    """
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

            position = c.parent_stmt.start_pos
            scope = c.parent_stmt.parent
            e = evaluate.follow_call_path(backtrack_path, scope, position)
            if not compare_array in e:
                # the `append`, etc. belong to other arrays
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
                # TODO needs extensive work, because this are iterables
                result += evaluate.follow_call_list(params)
        return result

    search_names = ['append', 'extend', 'insert'] if is_list else \
                                                            ['add', 'update']
    possible_stmts = []
    result = []
    for n in search_names:
        try:
            possible_stmts += module.used_names[n]
        except KeyError:
            continue
        for stmt in possible_stmts:
            result += check_calls(scan_array(stmt.get_assignment_calls(), n), n)

    return result

def check_array_instances(instance):
    ai = ArrayInstance(instance)
    return helpers.generate_param_array([ai])


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
                    items += temp.iter_content()
                    continue
            items += array.get_index_types()

        module = self.var_args.parent_stmt.get_parent_until()
        items += _check_array_additions(self.instance, module, str(self.instance.name) == 'list')
        return items
