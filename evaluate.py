import parsing
import itertools

class Exec(object):
    def __init__(self, base):
        self.base = base
    def get_parent_until(self, *args):
        return self.base.get_parent_until(*args)
        
class Instance(Exec):
    """ This class is used to evaluate instances. """

    def get_instance_vars(self):
        """
        Get the instance vars of a class. This includes the vars of all
        classes
        """
        n = []
        for s in self.base.subscopes:
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
        n += self.base.get_set_vars()
        return n

    def __repr__(self):
        return "<%s of %s>" % \
                (self.__class__.__name__, self.base)


class Execution(Exec):
    """
    This class is used to evaluate functions and their returns.
    """

    def get_return_types(self):
        """
        Get the return vars of a function.
        """
        result = []
        if isinstance(self.base, Execution):
            stmts = self.base.get_return_types()
        else:
            stmts = self.base.returns

        #n += self.function.get_set_vars()
        # these are the statements of the return functions
        for stmt in stmts:
            if isinstance(stmt, parsing.Class):
                # it might happen, that a function returns a Class and this
                # gets executed, therefore get the instance here.
                result.append(Instance(stmt))
            else:
                print 'addstmt', stmt
                result += follow_statement(stmt)

            print 'ret', stmt
        return result

    def __repr__(self):
        return "<%s of %s>" % \
                (self.__class__.__name__, self.base)


def get_names_for_scope(scope):
    """ Get all completions possible for the current scope. """
    compl = []
    start_scope = scope
    while scope:
        # class variables/functions are only availabe
        if not isinstance(scope, parsing.Class) or scope == start_scope:
            compl += scope.get_set_vars()
        scope = scope.parent
    print 'get_names_for_scope', scope, len(compl)
    return compl


def get_scopes_for_name(scope, name, search_global=False, search_func=None):
    """
    :return: List of Names. Their parents are the scopes, they are defined in.
    :rtype: list
    """
    def remove_statements(result):
        """
        This is the part where statements are being stripped.

        Due to lazy evaluation, statements like a = func; b = a; b() have to be
        evaluated.
        """
        res_new = []
        for r in result:
            if isinstance(r, parsing.Statement):
                scopes = follow_statement(r)
                res_new += remove_statements(scopes)
            else:
                res_new.append(r)
        return res_new

    if search_func:
        names = search_func()
    elif search_global:
        names = get_names_for_scope(scope)
    else:
        names = scope.get_set_vars()

    result = [c.parent for c in names if [name] == list(c.names)]
    return remove_statements(result)


def follow_statement(stmt, scope=None):
    """
    :param stmt: contains a statement
    :param scope: contains a scope. If not given, takes the parent of stmt.
    """
    if scope is None:
        scope = stmt.get_parent_until(parsing.Function)
    result = []
    calls = stmt.get_assignment_calls()
    print 'calls', calls, calls.values
    for tokens in calls:
        for tok in tokens:
            print 'tok', tok, type(tok), isinstance(tok,str)
            if not isinstance(tok, str):
                # the string tokens are just operations (+, -, etc.)
                result += follow_call(scope, tok)
    return result

def follow_call(scope, call):
    path = call.generate_call_list()

    current = next(path)
    result = []
    if isinstance(current, parsing.Array):
        """if current.arr_type == parsing.Array.EMPTY:
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
            """
        result.append(current)
    else:
        result = get_scopes_for_name(scope, current, search_global=True)
        pass

    print 'before', result
    result = follow_paths(path, result)
    print 'after result', result

    return result


def follow_paths(path, results):
    results_new = []
    try:
        if len(results) > 1:
            iter_paths = itertools.tee(path, len(results))
        else:
            iter_paths = [path]
        print 'enter', results, len(results)
        if len(results):
            for i, r in enumerate(results):
                print 1
                results_new += follow_path(iter_paths[i], r)
    except StopIteration:
        return results
    return results_new


def follow_path(path, input):
    """ takes a generator and tries to complete the path """
    def add_result(current, input):
        result = []
        if isinstance(current, parsing.Array):
            # this must be an execution, either () or []
            if current.arr_type == parsing.Array.LIST:
                result = []  # TODO eval lists
            else:
                # input must be a class or func - make an instance or execution
                if isinstance(input, parsing.Class):
                    result.append(Instance(input))
                else:
                    result.append(Execution(input))
        else:
            if isinstance(input, parsing.Function):
                # TODO check default function methods and return them
                result = []
            elif isinstance(input, Instance):
                result = get_scopes_for_name(input, current,
                                    search_func=input.get_instance_vars)
            elif isinstance(input, Execution):
                #try:
                    stmts = input.get_return_types()
                    print 'exec', stmts
                    for s in stmts:
                        result += add_result(current, s)
                #except AttributeError:
                #    dbg('cannot execute:', input)
            elif isinstance(input, parsing.Import):
                print 'dini mueter, steile griech!'
            else:
                # TODO check default class methods and return them also
                result = get_scopes_for_name(input, current)
        return result

    cur = next(path)
    print 'follow', input, cur

    return follow_paths(path, add_result(cur, input))


def dbg(*args):
    if debug_function:
        debug_function(*args)


debug_function = None
