import parsing
import __builtin__
import itertools


class Instance(object):
    """ This class is used to evaluate instances. """
    def __init__(self, cl):
        self.cl = cl

    def get_instance_vars(self):
        """
        Get the instance vars of a class. This includes the vars of all
        classes
        """
        n = []
        for s in self.cl.subscopes:
            try:
                # get the self name, if there's one
                self_name = s.params[0].used_vars[0].names[0]
            except:
                pass
            else:
                for n2 in s.get_set_vars():
                    # Only names with the selfname are being added.
                    # It is also important, that they have a len() of 2,
                    # because otherwise, they are just something else
                    if n2.names[0] == self_name and len(n2.names) == 2:
                        n.append(n2)
        n += self.cl.get_set_vars()
        return n


class Execution(object):
    """ This class is used to evaluate functions and their returns. """
    def __init__(self, function):
        self.cl = function

    def get_return_vars(self):
        """
        Get the instance vars of a class. This includes the vars of all
        classes
        """
        n = []
        n += self.function.get_set_vars()
        return n


def get_names_for_scope(scope):
    """ Get all completions possible for the current scope. """
    compl = []
    start_scope = scope
    while scope:
        # class variables/functions are only availabe
        if not isinstance(scope, parsing.Class) or scope == start_scope:
            compl += scope.get_set_vars()
        scope = scope.parent
    return compl


def get_scopes_for_name(scope, name, search_global=False):
    """
    :return: List of Names. Their parents are the scopes, they are defined in.
    :rtype: list
    """
    if search_global:
        names = get_names_for_scope(scope)
    else:
        names = scope.get_set_vars()

    result = [c.parent for c in names if [name] == list(c.names)]
    return result


# default: name in scope
# point: chaining
# execution: -> eval returns default & ?
def follow_statement(scope, stmt):
    arr = stmt.get_assignment_calls().values[0][0]
    print arr

    path = arr.generate_call_list()
    if debug_function:
        path, path_print = itertools.tee(path)
        dbg('')
        dbg('')
        dbg('calls:')
        for c in path_print:
            dbg(c)

        dbg('')
        dbg('')
        dbg('follow:')

    current = next(path)
    result = []
    if isinstance(current, parsing.Array):
        if current.arr_type == parsing.Array.EMPTY:
            # the normal case - no array type
            print 'length', len(current)
        elif current.arr_type == parsing.Array.LIST:
            result.append(__builtin__.list())
        elif current.arr_type == parsing.Array.SET:
            result.append(__builtin__.set())
        elif current.arr_type == parsing.Array.TUPLE:
            result.append(__builtin__.tuple())
        elif current.arr_type == parsing.Array.DICT:
            result.append(__builtin__.dict())
    else:
        result = get_scopes_for_name(scope, current, search_global=True)
        pass

    print result
    result = follow_paths(path, result)
    print result
    exit()

    return result


def follow_paths(path, results):
    results_new = []
    try:
        if len(results) > 1:
            iter_paths = itertools.tee(path, len(results))
        else:
            iter_paths = [path]
        for i, r in enumerate(results):
            results_new += follow_path(iter_paths[i], r)
    except StopIteration:
        return results
    return results_new


def follow_path(path, input):
    current = next(path)
    print 'follow', input, current
    result = []

    if isinstance(current, parsing.Array):
        # this must be an execution, either () or []
        if current.arr_type == parsing.Array.LIST:
            print 'dini mami'
            result = []  # TODO eval lists
        else:
            # input must be a class or func -> make an instance or execution
            if isinstance(input, parsing.Class):
                result.append(Instance(input))
            else:
                result.append(Execution(input))
    else:
        if isinstance(input, parsing.Function):
            # TODO check default function methods and return them
            result = []
        else:
            # TODO check default class methods and return them also
            if isinstance(input, Instance):
                result = input.get_instance_vars()
            elif isinstance(input, Execution):
                result = input.get_return_vars()
            else:
                result = get_scopes_for_name(input, current)

    return follow_paths(path, result)


def dbg(*args):
    if debug_function:
        debug_function(*args)


debug_function = None
