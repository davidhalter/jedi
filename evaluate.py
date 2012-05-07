"""
follow_statement -> follow_call -> follow_paths -> follow_path
'follow_import'

`get_names_for_scope` and `get_scopes_for_name` are search functions

TODO include super classes
TODO nonlocal statement
TODO doc
TODO list comprehensions, priority?
TODO care for *args **kwargs
TODO annotations
"""
from _compatibility import next

import itertools
import copy

import parsing
import modules
import debug
import builtin


memoize_caches = []


class MultiLevelStopIteration(Exception):
    pass


def clear_caches():
    for m in memoize_caches:
        m.clear()


def memoize_default(default=None):
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
                rv = function(*args, **kwargs)
                memo[key] = rv
                return rv
        return wrapper
    return func


class Executable(object):
    """ An instance is also an executable - because __init__ is called """
    def __init__(self, base, var_args=[]):
        self.base = base
        # the param input array
        self.var_args = var_args
        self.func = None

    def get_parent_until(self, *args):
        return self.base.get_parent_until(*args)

    @property
    def scope(self):
        """ Just try through the whole param array to find the own scope """
        for param in self.var_args:
            for call in param:
                try:
                    return call.parent_stmt.parent
                except AttributeError:  # if operators are there
                    pass
        raise IndexError('No params available')

    @memoize_default(default=[])
    def get_params(self):
        """
        This returns the params for an Execution/Instance and is injected as a
        'hack' into the parsing.Function class.
        This needs to be here, because Instance can have __init__ functions,
        which act the same way as normal functions
        """
        def gen_param_name_copy(param, keys=[], values=[], array_type=None):
            calls = parsing.Array(parsing.Array.NOARRAY,
                                    self.var_args.parent_stmt)
            calls.values = values
            calls.keys = keys
            calls.type = array_type
            new_param = copy.copy(param)
            new_param._assignment_calls_calculated = True
            new_param._assignment_calls = calls
            name = copy.copy(param.get_name())
            name.parent = new_param
            #print 'insert', i, name, calls.values, value, self.func.params
            return name

        result = []
        start_offset = 0
        #print '\n\nfunc_params', self.func, self.func.parent, self.func
        if isinstance(self.func, InstanceElement):
            # care for self -> just exclude it and add the instance
            start_offset = 1
            self_name = copy.copy(self.func.params[0].get_name())
            self_name.parent = self.func.instance
            result.append(self_name)

        param_dict = {}
        for param in self.func.params:
            param_dict[str(param.get_name())] = param
        # There may be calls, which don't fit all the params, this just ignores
        # it.
        var_arg_iterator = self.get_var_args_iterator()

        non_matching_keys = []
        for param in self.func.params[start_offset:]:
            # The value and key can both be null. There, the defaults apply.
            # args / kwargs will just be empty arrays / dicts, respectively.
            key, value = next(var_arg_iterator, (None, None))
            while key:
                try:
                    key_param = param_dict[str(key)]
                except KeyError:
                    non_matching_keys.append((key, value))
                else:
                    result.append(gen_param_name_copy(key_param,
                                                        values=[value]))
                key, value = next(var_arg_iterator, (None, None))

            #debug.warning('Too many arguments given.', value)

            assignment = param.get_assignment_calls().values[0]
            keys = []
            values = []
            array_type = None
            if assignment[0] == '*':
                # *args param
                array_type = parsing.Array.TUPLE
                if value:
                    values.append(value)
                for key, value in var_arg_iterator:
                    # iterate until a key argument is found
                    if key:
                        var_arg_iterator.push_back(key, value)
                        break
                    values.append(value)
            elif assignment[0] == '**':
                # **kwargs param
                array_type = parsing.Array.DICT
                if non_matching_keys:
                    keys, values = zip(*non_matching_keys)
            else:
                # normal param
                if value:
                    values = [value]

            result.append(gen_param_name_copy(param, keys=keys, values=values,
                                                array_type=array_type))
        return result

    def get_var_args_iterator(self):
        """
        Yields a key/value pair, the key is None, if its not a named arg.
        """
        def iterate():
            # var_args is typically an Array, and not a list
            for var_arg in self.var_args:
                # *args
                if var_arg[0] == '*':
                    arrays = follow_call_list(self.scope, [var_arg[1:]])
                    for array in arrays:
                        for field in array.get_contents():
                            yield None, field
                # **kwargs
                elif var_arg[0] == '**':
                    arrays = follow_call_list(self.scope, [var_arg[1:]])
                    for array in arrays:
                        for key, field in array.get_contents():
                            yield key[0].name, field
                    yield var_arg
                # normal arguments (including key arguments)
                else:
                    if len(var_arg) > 1 and var_arg[1] == '=':
                        # this is a named parameter
                        yield var_arg[0].name, var_arg[2:]
                    else:
                        yield None, var_arg

        class PushBackIterator(object):
            def __init__(self, iterator):
                self.pushes = []
                self.iterator = iterator

            def push_back(self, key, value):
                self.pushes.append((key,value))

            def __iter__(self):
                return self

            def next(self):
                """ Python 2 Compatibility """
                return self.__next__()

            def __next__(self):
                try:
                    return self.pushes.pop()
                except IndexError:
                    return next(self.iterator)

        return iter(PushBackIterator(iterate()))


    def set_param_cb(self, func):
        self.func = func
        func.param_cb = self.get_params


class Instance(Executable):
    """ This class is used to evaluate instances. """
    def __init__(self, base, var_args=[]):
        super(Instance, self).__init__(base, var_args)
        if var_args:
            self.set_init_params()

    def set_init_params(self):
        for sub in self.base.subscopes:
            if isinstance(sub, parsing.Function) \
                    and sub.name.get_code() == '__init__':
                self.set_param_cb(InstanceElement(self, sub))

    def get_func_self_name(self, func):
        """
        Returns the name of the first param in a class method (which is
        normally self
        """
        try:
            return func.params[0].used_vars[0].names[0]
        except:
            return None

    def get_defined_names(self):
        """
        Get the instance vars of a class. This includes the vars of all
        classes
        """
        def add_self_name(name):
            n = copy.copy(name)
            n.names = n.names[1:]
            names.append(InstanceElement(self, n))

        names = []
        # this loop adds the names of the self object, copies them and removes
        # the self.
        for s in self.base.subscopes:
            # get the self name, if there's one
            self_name = self.get_func_self_name(s)
            if self_name:
                for n in s.get_set_vars():
                    # Only names with the selfname are being added.
                    # It is also important, that they have a len() of 2,
                    # because otherwise, they are just something else
                    if n.names[0] == self_name and len(n.names) == 2:
                        add_self_name(n)

        for var in self.base.get_defined_names(as_instance=True):
            # functions are also instance elements
            if isinstance(var.parent, (parsing.Function)):
                var = InstanceElement(self, var)
            names.append(var)

        return names

    def parent(self):
        return self.base.parent

    def __repr__(self):
        return "<p%s of %s (var_args: %s)>" % \
                (self.__class__.__name__, self.base, len(self.var_args or []))


class InstanceElement(object):
    def __init__(self, instance, var):
        super(InstanceElement, self).__init__()
        self.instance = instance
        self.var = var

    @property
    def parent(self):
        return InstanceElement(self.instance, self.var.parent)

    @property
    def param_cb(self):
        return self.var.param_cb

    @param_cb.setter
    def param_cb(self, value):
        self.var.param_cb = value

    def __getattr__(self, name):
        return getattr(self.var, name)

    def __repr__(self):
        return "<%s of %s>" % (self.__class__.__name__, self.var)


class Class(object):
    def __init__(self, base):
        self.base = base

    def get_defined_names(self, as_instance=False):
        def in_iterable(name, iterable):
            for i in iterable:
                # only the last name is important, because these names have a
                # maximal length of 2, with the first one being `self`.
                if i.names[-1] == name.names[-1]:
                    return True
            return False

        names = self.base.get_defined_names()

        # check super classes:
        for s in self.base.supers:
            for cls in follow_statement(s):
                # get the inherited names
                if as_instance:
                    cls = Instance(cls)
                for i in cls.get_defined_names():
                    if not in_iterable(i, names):
                        names.append(i)
        return names

    def __getattr__(self, name):
        return getattr(self.base, name)

    def __repr__(self):
        return "<p%s of %s>" % (self.__class__.__name__, self.base)


class Execution(Executable):
    """
    This class is used to evaluate functions and their returns.
    """
    cache = {}

    @memoize_default(default=[])
    def get_return_types(self):
        """
        Get the return vars of a function.
        """
        stmts = []
        #print '\n\n', self.var_args, self.var_args.values, self.var_args.parent_stmt
        if isinstance(self.base, Class):
            # there maybe executions of executions
            stmts = [Instance(self.base, self.var_args)]
        else:
            # set the callback function to get the var_args
            self.set_param_cb(self.base)
            # don't do this with exceptions, as usual, because some deeper
            # exceptions could be catched - and I wouldn't know what happened.
            if hasattr(self.base, 'returns'):
                ret = self.base.returns
                for s in ret:
                    #temp, s.parent = s.parent, self
                    stmts += follow_statement(s)
                    #s.parent = temp

                # reset the callback function on exit
                # TODO how can we deactivate this again?
                #self.base.param_cb = None
            else:
                debug.warning("no execution possible", self.base)

        debug.dbg('exec stmts=', stmts, self.base, repr(self))

        return stmts

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
        values = self._array.values
        if index is not None:
            # This is indexing only one element, with a fixed index number,
            # otherwise it just ignores the index (e.g. [1+1])
            try:
                index_nr = int(index.get_only_subelement().name)
                values = [self._array[index_nr]]
            except:
                pass
        scope = self._array.parent_stmt.parent
        return follow_call_list(scope, values)

    def get_exact_index_types(self, index):
        values = [self._array[index]]
        scope = self._array.parent_stmt.parent
        return follow_call_list(scope, values)

    def get_defined_names(self):
        """ This method generates all ArrayElements for one parsing.Array. """
        # array.type is a string with the type, e.g. 'list'
        scope = get_scopes_for_name(builtin.Builtin.scope, self._array.type)[0]
        names = scope.get_defined_names()
        return [ArrayElement(n) for n in names]

    def get_contents(self):
        return self._array

    def __repr__(self):
        return "<p%s of %s>" % (self.__class__.__name__, self._array)


class ArrayElement(object):
    def __init__(self, name):
        super(ArrayElement, self).__init__()
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


def get_defined_names_for_position(obj, position):
    names = obj.get_defined_names()
    if not position:
        return names
    names_new = []
    for n in names:
        if (n.line_nr, n.indent) < position:
            names_new.append(n)
    return names_new


def get_names_for_scope(scope, position=None, star_search=True):
    """
    Get all completions possible for the current scope.
    The star search option is only here to provide an optimization. Otherwise
    the whole thing would probably start a little recursive madness.
    """
    start_scope = scope
    while scope:
        # class variables/functions are only available
        if (not isinstance(scope, Class) or scope == start_scope) \
                and not isinstance(scope, parsing.Flow):
            try:
                yield scope, get_defined_names_for_position(scope, position)
            except StopIteration:
                raise MultiLevelStopIteration('StopIteration raised somewhere')
        scope = scope.parent

    # add star imports
    if star_search:
        for s in remove_star_imports(start_scope.get_parent_until()):
            for g in get_names_for_scope(s, star_search=False):
                yield g

    # add builtins to the global scope
    builtin_scope = builtin.Builtin.scope
    yield builtin_scope, builtin_scope.get_defined_names()


def get_scopes_for_name(scope, name_str, position=None, search_global=False):
    """
    :param position: Position of the last statement ->tuple of line, indent
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
            if isinstance(r, parsing.Statement) \
                    or isinstance(r, InstanceElement) \
                    and isinstance(r.var, parsing.Statement):
                # global variables handling
                if r.is_global():
                    for token_name in r.token_list[1:]:
                        if isinstance(token_name, parsing.Name):
                            res_new += get_scopes_for_name(r.parent,
                                                            str(token_name))
                else:
                    scopes = follow_statement(r, seek_name=name_str)
                    res_new += remove_statements(scopes)
            else:
                if isinstance(r, parsing.Class):
                    r = Class(r)
                res_new.append(r)
        debug.dbg('sfn remove, new: %s, old: %s' % (res_new, result))
        return res_new

    def filter_name(scope_generator):
        def handle_non_arrays(name):
            result = []
            par = name.parent
            if isinstance(par, parsing.Flow):
                if par.command == 'for':
                    # take the first statement (for has always only
                    # one, remember `in`). And follow it. After that,
                    # get the types which are in the array
                    arrays = follow_statement(par.inits[0])
                    for array in arrays:
                        in_vars = array.get_index_types()
                        if len(par.set_vars) > 1:
                            var_arr = par.set_stmt.get_assignment_calls()
                            result += assign_tuples(var_arr, in_vars, name_str)
                        else:
                            result += in_vars
                else:
                    debug.warning('Flow: Why are you here? %s' % par.command)
            elif isinstance(par, parsing.Param) \
                    and isinstance(par.parent.parent, parsing.Class) \
                    and par.position == 0:
                # this is where self gets added - this happens at another
                # place, if the var_args are clear. But some times the class is
                # not known. Therefore set self.
                result.append(Instance(Class(par.parent.parent)))
                result.append(par)
            else:
                result.append(par)
            return result

        result = []
        # compare func uses the tuple of line/indent = row/column
        comparison_func = lambda name: (name.line_nr, name.indent)
        for scope, name_list in scope_generator:
            # here is the position stuff happening (sorting of variables)
            for name in sorted(name_list, key=comparison_func, reverse=True):
                if name_str == name.get_code():
                    result += handle_non_arrays(name)
                    #print name, name.parent.parent, scope
                    # this means that a definition was found and is not e.g.
                    # in if/else.
                    if name.parent.parent == scope:
                        break
            # if there are results, ignore the other scopes
            if result:
                break
        debug.dbg('sfn filter', name_str, result)
        return result

    if search_global:
        scope_generator = get_names_for_scope(scope, position=position)
    else:
        if position:
            names = get_defined_names_for_position(scope, position)
        else:
            names = scope.get_defined_names()
        scope_generator = iter([(scope, names)])
    #print ' ln', position

    return remove_statements(filter_name(scope_generator))


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


def assign_tuples(tup, results, seek_name):
    """
    This is a normal assignment checker. In python functions and other things
    can return tuples:
    >>> a, b = 1, ""
    >>> a, (b, c) = 1, ("", 1.0)

    Here, if seek_name is "a", the number type will be returned.
    The first part (before `=`) is the param tuples, the second one result.

    :type tup: parsing.Array
    """
    def eval_results(index):
        types = []
        for r in results:
            if hasattr(r, "get_exact_index_types"):
                types += r.get_exact_index_types(index)
            else:
                debug.warning("assign tuples: invalid tuple lookup")
        return types

    result = []
    if tup.type == parsing.Array.NOARRAY:
        # here we have unnessecary braces, which we just remove
        arr = tup.get_only_subelement()
        result = assign_tuples(arr, results, seek_name)
    else:
        for i, t in enumerate(tup):
            # used in assignments. there is just one call and no other things,
            # therefor we can just assume, that the first part is important.
            if len(t) != 1:
                raise AttributeError('Array length should be 1')
            t = t[0]

            # check the left part, if it's still tuples in it or a Call
            if isinstance(t, parsing.Array):
                # these are "sub" tuples
                result += assign_tuples(t, eval_results(i), seek_name)
            else:
                if t.name.names[-1] == seek_name:
                    result += eval_results(i)
    return result


@memoize_default(default=[])
def follow_statement(stmt, scope=None, seek_name=None):
    """
    :param stmt: contains a statement
    :param scope: contains a scope. If not given, takes the parent of stmt.
    """
    if scope is None:
        scope = stmt.get_parent_until(parsing.Function, Execution,
                                        parsing.Class, Instance,
                                        InstanceElement)
    debug.dbg('follow_stmt', stmt, 'in', scope, seek_name)

    call_list = stmt.get_assignment_calls()
    debug.dbg('calls', call_list, call_list.values)
    result = follow_call_list(scope, call_list)

    # assignment checking is only important if the statement defines multiple
    # variables
    if len(stmt.get_set_vars()) > 1 and seek_name and stmt.assignment_details:
        # TODO this should have its own call_list, because call_list can also
        # return 3 results for 2 variables.
        new_result = []
        for op, set_vars in stmt.assignment_details:
            new_result += assign_tuples(set_vars, result, seek_name)
        result = new_result
    return result


def follow_call_list(scope, call_list):
    """
    The call_list has a special structure.
    This can be either `parsing.Array` or `list of list`.
    It is used to evaluate a two dimensional object, that has calls, arrays and
    operators in it.
    """
    if parsing.Array.is_type(call_list, parsing.Array.TUPLE,
                                        parsing.Array.DICT):
        # Tuples can stand just alone without any braces. These would be
        # recognized as separate calls, but actually are a tuple.
        result = follow_call(scope, call_list)
    else:
        result = []
        for calls in call_list:
            for call in calls:
                if parsing.Array.is_type(call, parsing.Array.NOARRAY):
                    result += follow_call_list(scope, call)
                else:
                    if not isinstance(call, str):
                        # The string tokens are just operations (+, -, etc.)
                        result += follow_call(scope, call)
    return set(result)


def follow_call(scope, call):
    """ Follow a call is following a function, variable, string, etc. """
    path = call.generate_call_list()

    position = (call.parent_stmt.line_nr, call.parent_stmt.indent)
    current = next(path)
    if isinstance(current, parsing.Array):
        result = [Array(current)]
    else:
        # TODO add better care for int/unicode, now str/float are just used
        # instead
        if not isinstance(current, parsing.NamePart):
            if current.type == parsing.Call.STRING:
                scopes = get_scopes_for_name(builtin.Builtin.scope, 'str')
            elif current.type == parsing.Call.NUMBER:
                scopes = get_scopes_for_name(builtin.Builtin.scope, 'float')
            else:
                debug.warning('unknown type:', current.type, current)
            # make instances of those number/string objects
            scopes = [Instance(s) for s in scopes]
        else:
            # this is the first global lookup
            scopes = get_scopes_for_name(scope, current, position=position,
                                            search_global=True)
        result = strip_imports(scopes)

        if result != scopes:
            # reset the position, when imports where stripped
            position = None

    debug.dbg('call before result %s, current %s, scope %s'
                                % (result, current, scope))
    result = follow_paths(path, result, position=position)

    return result


def follow_paths(path, results, position=None):
    results_new = []
    if results:
        if len(results) > 1:
            iter_paths = itertools.tee(path, len(results))
        else:
            iter_paths = [path]

        for i, r in enumerate(results):
            fp = follow_path(iter_paths[i], r, position=position)
            if fp is not None:
                results_new += fp
            else:
                # this means stop iteration 
                return results
    return results_new


def follow_path(path, scope, position=None):
    """
    Takes a generator and tries to complete the path.
    """
    # current is either an Array or a Scope
    try:
        current = next(path)
    except StopIteration:
        return None
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
        else:
            # curly braces are not allowed, because they make no sense
            debug.warning('strange function call with {}', current, scope)
    else:
        if isinstance(scope, parsing.Function):
            # TODO check default function methods and return them
            result = []
        else:
            # TODO check magic class methods and return them also
            # this is the typical lookup while chaining things
            result = strip_imports(get_scopes_for_name(scope, current,
                                                        position=position))
    return follow_paths(path, result, position=position)


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
        scopes = follow_path(iter(rest), scope)
    else:
        scopes = [scope]

    new = []
    for scope in scopes:
        new += remove_star_imports(scope)
    scopes += new

    debug.dbg('after import', scopes, rest)
    return scopes


def remove_star_imports(scope):
    """
    TODO doc
    """
    modules = strip_imports(i for i in scope.get_imports() if i.star)
    new = []
    for m in modules:
        new += remove_star_imports(m)
    modules += new

    # filter duplicate modules
    return set(modules)
