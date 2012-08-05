"""
For dynamic completion.
"""
import parsing
import evaluate

# This is something like the sys.path, but only for searching params. It means
# that this is the order in which Jedi searches params.
search_param_modules = ['.']

def search_params(param):
    def scan_array(arr):
        """ Returns the function Calls that match func_name """
        result = []
        for sub in arr:
            for s in sub:
                if isinstance(s, parsing.Array):
                    result += scan_array(s)
                elif isinstance(s, parsing.Call):
                    if str(s.name) == func_name:
                        result.append(s)
        return result

    def get_params_for_module(module):
        result = []
        try:
            possible_stmts = current_module.used_names[func_name]
        except KeyError:
            return []

        calls = []
        for stmt in possible_stmts:
            calls += scan_array(stmt.get_assignment_calls())

        for c in calls:
            if not c.execution:
                continue

            # now check if the call is actually the same method
            c.execution, temp = None, c.execution
            possible_executions = evaluate.follow_call(c)
            is_same_method = False
            for e in possible_executions:
                is_same_method = e == func \
                    or isinstance(e, evaluate.Function) and e.base_func == func
            if not is_same_method:
                continue
            c.execution = temp

            try:
                p = c.execution[param_nr]
            except IndexError:
                pass
            else:
                result += evaluate.follow_call_list([p])
        return result

    func = param.get_parent_until(parsing.Function)
    func_name = str(func.name)

    current_module = param.get_parent_until()
    for i, p in enumerate(func.params):
        param_nr = i

    result = get_params_for_module(current_module)

    # TODO check other modules
    return result
