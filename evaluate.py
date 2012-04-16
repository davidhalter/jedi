"""
follow_statement -> follow_call -> follow_paths -> follow_path
'follow_import'

`get_names_for_scope` and `get_scopes_for_name` are search functions

TODO include super classes
"""
# python2.5 compatibility
try:
    next
except NameError:
    def next(obj):
        return obj.next()

import itertools

import parsing
import modules
import debug
import builtin


memoize_caches = []


def clear_caches():
    for m in memoize_caches:
        m.clear()


def memoize(default=None):
    """
    This is a typical memoization decorator, BUT there is one difference:
    To prevent recursion it sets defaults.

    Preventing recursion is in this case the much bigger use than speed. I
    don't think, that there is a big speed difference, but there are many cases
    where recursion could happen (think about a = b; b = a).
    """
    def func(function):
        memo = {}
        memoize_caches.append(memo)

        def wrapper(*args):
            if args in memo:
                return memo[args]
            else:
                memo[args] = default
                rv = function(*args)
                memo[args] = rv
                return rv
        return wrapper
    return func


class Exec(object):
    def __init__(self, base, params=None):
        self.base = base
        self.params = params

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

    def get_defined_names(self):
        return self.get_set_vars()

    def __repr__(self):
        return "<%s of %s>" % \
                (self.__class__.__name__, self.base)


class Array(object):
    """
    Used as a mirror to parsing.Array, if needed. It defines some getter
    methods which are important in this module.
    """
    def __init__(self, array):
        self._array = array

    def get_index_type(self, index):
        #print self._array.values, index.values
        values = self._array.values
        #print 'ui', index.values, index.values[0][0].type
        iv = index.values
        if len(iv) == 1 and len(iv[0]) == 1 and iv[0][0].type == \
                parsing.Call.NUMBER and self._array.type != parsing.Array.DICT:
            try:
                values = [self._array.values[int(iv[0][0].name)]]
            except:
                pass
        scope = self._array.parent_stmt.parent
        return follow_call_list(scope, values)

    def get_defined_names(self):
        """ This method generates all ArrayElements for one parsing.Array. """
        # array.type is a string with the type, e.g. 'list'
        scope = get_scopes_for_name(builtin.Builtin.scope, self._array.type)[0]
        names = scope.get_defined_names()
        return [ArrayElement(n) for n in names]

    def __repr__(self):
        return "<%s of %s>" % (self.__class__.__name__, self._array)


class ArrayElement(object):
    def __init__(self, name):
        self.name = name

    @property
    def parent(self):
        raise NotImplementedError("This shouldn't happen")
        return

    @property
    def returns(self):
        return self.name.parent.returns

    @property
    def names(self):
        return self.name.names

    def __repr__(self):
        return "<%s of %s>" % (self.__class__.__name__, self.name)


class Execution(Exec):
    """
    This class is used to evaluate functions and their returns.
    """
    cache = {}

    @memoize(default=[])
    def get_return_types(self):
        """
        Get the return vars of a function.
        """
        def remove_executions(scope, get_returns=False):
            stmts = []
            if isinstance(scope, parsing.Class):
                # there maybe executions of executions
                stmts = [Instance(scope, self.params)]
            else:
                if get_returns:
                    ret = scope.returns
                    for s in ret:
                        #for stmt in follow_statement(s):
                        #    stmts += remove_executions(stmt)
                        stmts += follow_statement(s)
                else:
                    stmts.append(scope)
            return stmts

        result = remove_executions(self.base, True)
        debug.dbg('exec stmts=', result, self.base, repr(self))

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
            compl += scope.get_defined_names()
        scope = scope.parent

    # add builtins to the global scope
    compl += builtin.Builtin.scope.get_defined_names()
    #print 'gnfs', scope, compl
    return compl


def get_scopes_for_name(scope, name, search_global=False):
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
        debug.dbg('sfn remove', res_new, result)
        return res_new

    def filter_name(scopes):
        # the name is already given in the parent function
        result = []
        for scope in scopes:
            #if isinstance(scope, parsing.Import):
            #    try:
            #        debug.dbg('star import', scope)
            #        i = follow_import(scope).get_defined_names()
            #    except modules.ModuleNotFound:
            #        debug.dbg('StarImport not found: ' + str(scope))
            #    else:
            #        result += filter_name(i)
            #else:
            if [name] == list(scope.names):
                if isinstance(scope, ArrayElement):
                    result.append(scope)
                else:
                    par = scope.parent
                    if isinstance(par, parsing.Flow):
                        # TODO get Flow data, which is defined by the loop
                        # (or with)
                        pass
                    elif isinstance(par, parsing.Param):
                        if isinstance(par.parent.parent, parsing.Class) \
                                and par.position == 0:
                            # this is where self is added
                            result.append(Instance(par.parent.parent))
                        else:
                            # TODO get function data
                            pass
                    else:
                        result.append(scope.parent)
        debug.dbg('sfn filter', result)
        return result

    if search_global:
        names = get_names_for_scope(scope)
    else:
        names = scope.get_defined_names()

    return remove_statements(filter_name(names))


def strip_imports(scopes):
    """
    Here we strip the imports - they don't get resolved necessarily, but star
    imports are looked at here.
    """
    result = []
    for s in scopes:
        if isinstance(s, parsing.Import):
            print 'dini mueter, steile griech!'
            try:
                new_scopes = follow_import(s)
            except modules.ModuleNotFound:
                debug.dbg('Module not found: ' + str(s))
            else:
                result += new_scopes
                for n in new_scopes:
                        result += strip_imports(i for i in n.get_imports()
                                                                if i.star)
        else:
            result.append(s)
    return result


@memoize(default=[])
def follow_statement(stmt, scope=None):
    """
    :param stmt: contains a statement
    :param scope: contains a scope. If not given, takes the parent of stmt.
    """
    if scope is None:
        scope = stmt.get_parent_until(parsing.Function)
    call_list = stmt.get_assignment_calls()
    debug.dbg('calls', call_list, call_list.values)
    return follow_call_list(scope, call_list)


def follow_call_list(scope, call_list):
    """ The call list has a special structure """
    result = []
    for calls in call_list:
        for call in calls:
            if not isinstance(call, str):
                # the string tokens are just operations (+, -, etc.)
                result += follow_call(scope, call)
    return result


def follow_call(scope, call):
    """ Follow a call is following a function, variable, string, etc. """
    path = call.generate_call_list()

    current = next(path)
    if isinstance(current, parsing.Array):
        result = [Array(current)]
    else:
        # TODO add better care for int/unicode, now str/float are just used
        # instead
        not_name_part = not isinstance(current, parsing.NamePart)
        if not_name_part and current.type == parsing.Call.STRING:
            scopes = get_scopes_for_name(builtin.Builtin.scope, 'str')
        elif not_name_part and current.type == parsing.Call.NUMBER:
            scopes = get_scopes_for_name(builtin.Builtin.scope, 'float')
        else:
            scopes = get_scopes_for_name(scope, current, search_global=True)
        result = strip_imports(scopes)

    debug.dbg('call before', result, current, scope)
    result = follow_paths(path, result)

    return result


def follow_paths(path, results):
    results_new = []
    try:
        if results:
            if len(results) > 1:
                iter_paths = itertools.tee(path, len(results))
            else:
                iter_paths = [path]
            for i, r in enumerate(results):
                results_new += follow_path(iter_paths[i], r)
    except StopIteration:
        #if isinstance(s, parsing.Array):
        #    completions += s.
        #else:
        return results
    return results_new


def follow_path(path, input):
    """
    Takes a generator and tries to complete the path.
    """
    # current is either an Array or a Scope
    current = next(path)
    debug.dbg('follow', current, input)

    def filter_result(scope):
        result = []
        if isinstance(current, parsing.Array):
            # this must be an execution, either () or []
            if current.type == parsing.Array.LIST:
                result = scope.get_index_type(current)
            elif current.type not in [parsing.Array.DICT]:
                # scope must be a class or func - make an instance or execution
                debug.dbg('befexec', scope)
                exe = Execution(scope, current)
                result = strip_imports(exe.get_return_types())
                debug.dbg('exec', result)
                #except AttributeError:
                #    debug.dbg('cannot execute:', scope)
            else:
                # curly braces are not allowed, because they make no sense
                debug.warning('strange function call with {}', current, scope)
        else:
            if isinstance(scope, parsing.Function):
                # TODO check default function methods and return them
                result = []
            else:
                # TODO check magic class methods and return them also
                result = strip_imports(get_scopes_for_name(scope, current))
        return result
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

    loaded_in = _import.get_parent_until()

    scope, rest = modules.find_module(loaded_in, ns_list)
    if rest:
        scopes = follow_path(rest.__iter__(), scope)
    else:
        scopes = [scope]

    debug.dbg('after import', scopes, rest)
    return scopes
