"""
follow_statement -> follow_call -> follow_paths -> follow_path
'follow_import'

`get_names_for_scope` and `get_scopes_for_name` are search functions

TODO include super classes
"""
from _compatibility import next

import itertools
import copy

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

        def wrapper(*args, **kwargs):
            key = (args, frozenset(kwargs.items()))
            if key in memo:
                return memo[key]
            else:
                memo[key] = default
                rv = function(*args)
                memo[key] = rv
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
        stmts = []
        #print '\n\n', self.params, self.params.values, self.params.parent_stmt
        if isinstance(self.base, parsing.Class):
            # there maybe executions of executions
            stmts = [Instance(self.base, self.params)]
        else:
            # set the callback function to get the params
            self.base.param_cb = self.get_params
            ret = self.base.returns
            for s in ret:
                #temp, s.parent = s.parent, self
                stmts += follow_statement(s)
                #s.parent = temp

            # reset the callback function on exit
            self.base.param_cb = None

        debug.dbg('exec stmts=', stmts, self.base, repr(self))

        #print stmts
        return stmts

    @memoize(default=[])
    def get_params(self):
        result = []
        for i, param in enumerate(self.base.params):
            try:
                value = self.params.values[i]
            except IndexError:
                # This means, that there is no param in the call. So we just
                # ignore it and take the default params.
                result.append(param.get_name())
            else:
                new_param = copy.copy(param)
                calls = parsing.Array(parsing.Array.EMPTY,
                                        self.params.parent_stmt)
                calls.values = [value]
                new_param._assignment_calls = calls
                name = copy.copy(param.get_name())
                name.parent = new_param
                result.append(name)
        return result

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

    def get_index_types(self, index=None):
        #print self._array.values, index.values
        values = self._array.values
        #print 'ui', index.values, index.values[0][0].type
        if index is not None:
            # This is indexing only one element, with a fixed index number
            iv = index.values
            if len(iv) == 1 and len(iv[0]) == 1 \
                    and iv[0][0].type == parsing.Call.NUMBER \
                    and self._array.type != parsing.Array.DICT:
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

    @property
    def returns(self):
        return self.name.parent.returns

    @property
    def names(self):
        return self.name.names

    def __repr__(self):
        return "<%s of %s>" % (self.__class__.__name__, self.name)


def get_names_for_scope(scope, star_search=True):
    """
    Get all completions possible for the current scope.
    The star search option is only here to provide an optimization. Otherwise
    the whole thing would make a little recursive maddness
    """
    compl = []
    start_scope = scope
    while scope:
        # class variables/functions are only availabe
        if not isinstance(scope, parsing.Class) or scope == start_scope:
            compl += scope.get_defined_names()
        scope = scope.parent

    # add builtins to the global scope
    compl += builtin.Builtin.scope.get_defined_names()

    # add star imports
    if star_search:
        for s in remove_star_imports(start_scope.get_parent_until()):
            compl += get_names_for_scope(s, star_search=False)
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
        debug.dbg('sfn remove, new: %s, old: %s' % (res_new, result))
        return res_new

    def filter_name(scopes):
        # the name is already given in the parent function
        result = []
        for scope in scopes:
            if [name] == list(scope.names):
                if isinstance(scope, ArrayElement):
                    result.append(scope)
                else:
                    par = scope.parent
                    if isinstance(par, parsing.Flow):
                        # TODO get Flow data, which is defined by the loop
                        # (or with)
                        if par.command == 'for':
                            # take the first statement (for has always only
                            # one, remember `in`). And follow it. After that,
                            # get the types which are in the array
                            arrays = follow_statement(par.inits[0])
                            for array in arrays:
                                result += array.get_index_types()
                        else:
                            debug.warning('Why are you here? %s' % par.command)
                    elif isinstance(par, parsing.Param) \
                            and isinstance(par.parent.parent, parsing.Class) \
                            and par.position == 0:
                        # this is where self gets added
                        result.append(Instance(par.parent.parent))
                        result.append(par)
                    else:
                        result.append(par)
        debug.dbg('sfn filter', result)
        return result

    if search_global:
        names = get_names_for_scope(scope)
    else:
        names = scope.get_defined_names()

    return remove_statements(filter_name(names))


def strip_imports(scopes):
    """
    Here we strip the imports - they don't get resolved necessarily.
    Really used anymore?
    """
    result = []
    for s in scopes:
        if isinstance(s, parsing.Import):
            #print 'dini mueter, steile griech!'
            try:
                result += follow_import(s)
            except modules.ModuleNotFound:
                debug.warning('Module not found: ' + str(s))
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
        scope = stmt.get_parent_until(parsing.Function, Execution,
                                        parsing.Class, Instance)
    call_list = stmt.get_assignment_calls()
    debug.dbg('calls', call_list, call_list)
    result = set(follow_call_list(scope, call_list))

    if stmt.assignment_details:
        new_result = []
        for op, set_vars in stmt.assignment_details:
            stmt.assignment_details[0]
            #print '\n\nlala', op, set_vars.values, call_list.values
            #print stmt, scope
        #result = new_result
    return result


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

    debug.dbg('call before result %s, current %s, scope %s'
                                % (result, current, scope))
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


def follow_path(path, scope):
    """
    Takes a generator and tries to complete the path.
    """
    # current is either an Array or a Scope
    current = next(path)
    debug.dbg('follow', current, scope)

    result = []
    if isinstance(current, parsing.Array):
        # this must be an execution, either () or []
        if current.type == parsing.Array.LIST:
            result = scope.get_index_types(current)
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
            # TODO this is never reached, just remove it?
            # TODO check default function methods and return them
            result = []
        else:
            # TODO check magic class methods and return them also
            result = strip_imports(get_scopes_for_name(scope, current))
    return follow_paths(path, result)


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

    new = []
    for scope in scopes:
        new += remove_star_imports(scope)
    scopes += new

    debug.dbg('after import', scopes, rest)
    return scopes


def remove_star_imports(scope):
    modules = strip_imports(i for i in scope.get_imports() if i.star)
    new = []
    for m in modules:
        new += remove_star_imports(m)
    modules += new

    # filter duplicate modules
    return set(modules)
