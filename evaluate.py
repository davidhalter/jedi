import itertools

import parsing
import modules
import debug


class Exec(object):
    def __init__(self, base):
        self.base = base
    def get_parent_until(self, *args):
        return self.base.get_parent_until(*args)


class Instance(Exec):
    """ This class is used to evaluate instances. """

    def get_set_vars(self):
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

    cache = {}
    def get_return_types(self):
        """
        Get the return vars of a function.
        """
        def remove_executions(scope, get_returns=False):
            if isinstance(scope, Execution):
                # there maybe executions of executions
                stmts = scope.get_return_types()
            else:
                if get_returns:
                    stmts = scope.returns
                else:
                    stmts = [scope]
            return stmts

        # check cache
        try:
            return Execution.cache[self.base]
        except KeyError:
            # cache is not only here as a cache, but also to prevent an
            # endless recursion.
            Execution.cache[self.base] = []

        result = []
        stmts = remove_executions(self.base, True)
        print 'stmts=', stmts, self.base, repr(self)

        #n += self.function.get_set_vars()
        # these are the statements of the return functions
        for stmt in stmts:
            if isinstance(stmt, parsing.Class):
                # it might happen, that a function returns a Class and this
                # gets executed, therefore get the instance here.
                result.append(Instance(stmt))
            else:
                print 'addstmt', stmt
                for followed in follow_statement(stmt):
                    print 'followed', followed
                    result += remove_executions(followed)

            print 'ret', stmt
        Execution.cache[self.base] = result
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

    def filter_name(scopes):
        # the name is already given in the parent function
        result = []
        for scope in scopes:
            if isinstance(scope, parsing.Import):
                try:
                    i = follow_import(scope).get_defined_names()
                except modules.ModuleNotFound:
                    debug.dbg('StarImport not found: ' + str(scope))
                else:
                    result += filter_name(i)
            else:
                if [name] == list(scope.names):
                    result.append(scope.parent)
        return result

    if search_func:
        names = search_func()
    elif search_global:
        names = get_names_for_scope(scope)
    else:
        names = scope.get_set_vars()

    # TODO here are the star imports handled, we need to get the names here.
    # This means things like from pylab import *
    return remove_statements(filter_name(names))


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
                results_new += follow_path(iter_paths[i], r)
    except StopIteration:
        return results
    return results_new


def follow_path(path, input):
    """
    takes a generator and tries to complete the path
    """
    def add_results(scopes):
        """ Here we follow the results - to get what we really want """
        result = []
        for s in scopes:
            if isinstance(s, parsing.Import):
                print 'dini mueter, steile griech!'
                try:
                    result.append(follow_import(s))
                except modules.ModuleNotFound:
                    debug.dbg('Module not found: ' + str(s))
            else:
                result.append(s)
        return result

    def filter_result(scope):
        result = []
        if isinstance(current, parsing.Array):
            # this must be an execution, either () or []
            if current.arr_type == parsing.Array.LIST:
                result = []  # TODO eval lists
            else:
                # scope must be a class or func - make an instance or execution
                if isinstance(scope, parsing.Class):
                    result.append(Instance(scope))
                else:
                    #try:
                    print '\n\n\n\n\nbefexec', scope
                    stmts = add_results(Execution(scope).get_return_types())
                    debug.dbg('exec', stmts)
                    result = stmts
                    #except AttributeError:
                    #    debug.dbg('cannot execute:', scope)
        else:
            if isinstance(scope, parsing.Function):
                # TODO check default function methods and return them
                result = []
            else:
                # TODO check magic class methods and return them also
                result = add_results(get_scopes_for_name(scope, current))
        return result

    current = next(path)
    print 'follow', input, current

    return follow_paths(path, filter_result(input))


def follow_import(_import):
    """
    follows a module name and returns the parser.
    :param _import: The import statement.
    :type _import: parsing.Import
    """
    # set path together
    ns_list = []
    if _import.from_ns:
        ns_list += _import.from_ns.names
    if _import.namespace:
        ns_list += _import.namespace.names

    scope, rest = modules.find_module(ns_list)
    if rest:
        scope = follow_path(rest.__iter__(), scope)

    debug.dbg('after import', scope, rest)
    return scope

