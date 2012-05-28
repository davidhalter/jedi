"""
follow_statement -> follow_call -> follow_paths -> follow_path
'follow_import'

`get_names_for_scope` and `get_scopes_for_name` are search functions

TODO doc
TODO list comprehensions, priority?
TODO evaluate asserts (type safety)

python 3 stuff:
TODO class decorators
TODO annotations ? how ? type evaluation and return?
TODO nonlocal statement

TODO getattr / __getattr__ / __getattribute__ ?
TODO descriptors
TODO __call__
"""
from _compatibility import next, property

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

    def get_parent_until(self, *args):
        return self.base.get_parent_until(*args)

    @property
    def parent(self):
        return self.base.parent


class Instance(Executable):
    """ This class is used to evaluate instances. """

    @memoize_default()
    def get_init_execution(self, func):
        if isinstance(func, parsing.Function):
            #self.set_param_cb(InstanceElement(self, Function.create(sub)))
            instance_el = InstanceElement(self, Function.create(func))
            return Execution(instance_el, self.var_args)
        else:
            return func

    def get_subscope_by_name(self, name):
        for sub in reversed(self.base.subscopes):
            if sub.name.get_code() == name:
                return sub
        raise KeyError("Couldn't find subscope.")

    def get_func_self_name(self, func):
        """
        Returns the name of the first param in a class method (which is
        normally self
        """
        try:
            return func.params[0].used_vars[0].names[0]
        except IndexError:
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
        for sub in self.base.subscopes:
            # get the self name, if there's one
            self_name = self.get_func_self_name(sub)
            if self_name:
                # check the __init__ function
                if self.var_args and sub.name.get_code() == '__init__':
                    sub = self.get_init_execution(sub)
                for n in sub.get_set_vars():
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

    @property
    def line_nr(self):
        return self.base.line_nr

    @property
    def indent(self):
        return self.base.indent

    @property
    def name(self):
        return self.base.name

    def __repr__(self):
        return "<e%s of %s (var_args: %s)>" % \
                (self.__class__.__name__, self.base, len(self.var_args or []))


class InstanceElement(object):
    def __init__(self, instance, var):
        super(InstanceElement, self).__init__()
        self.instance = instance
        self.var = var

    @property
    def parent(self):
        return InstanceElement(self.instance, self.var.parent)

    def get_parent_until(self, *classes):
        scope = self.var.get_parent_until(*classes)
        return InstanceElement(self.instance, scope)

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

    @property
    def name(self):
        return self.base.name

    def __getattr__(self, name):
        return getattr(self.base, name)

    def __repr__(self):
        return "<e%s of %s>" % (self.__class__.__name__, self.base)


class Function(object):
    """
    """
    def __init__(self, func, is_decorated):
        """ This should not be called directly """
        self.base_func = func
        self.func = self.process_decorators(is_decorated)

    @staticmethod
    @memoize_default()
    def create(func, is_decorated=False):
        return Function(func, is_decorated)

    def __getattr__(self, name):
        return getattr(self.func, name)

    def process_decorators(self, is_decorated):
        """ Returns the function, that is to be executed in the end """
        func = self.base_func

        # only enter it, if has not already been processed
        if not is_decorated:
            for dec in reversed(self.base_func.decorators):
                debug.dbg('decorator:', dec, func)
                dec_results = follow_statement(dec)
                if not len(dec_results):
                    debug.warning('decorator func not found', self.base_func)
                    return []
                if len(dec_results) > 1:
                    debug.warning('multiple decorators found', self.base_func,
                                                            dec_results)
                decorator = dec_results.pop()
                # create param array
                old_func = Function.create(func, is_decorated=True)
                params = parsing.Array(parsing.Array.NOARRAY, old_func)
                params.values = [[old_func]]
                wrappers = Execution(decorator, params).get_return_types()
                if not len(wrappers):
                    debug.warning('no wrappers found', self.base_func)
                    return []
                if len(wrappers) > 1:
                    debug.warning('multiple wrappers found', self.base_func,
                                                                wrappers)
                # this is here, that the wrapper gets executed
                func = wrappers[0]

                debug.dbg('decorator end')
        if func != self.base_func:
            return Function.create(func)
        else:
            return func

    def __repr__(self):
        return "<e%s of %s>" % (self.__class__.__name__, self.func)


class Execution(Executable):
    """
    This class is used to evaluate functions and their returns.

    This is the most complicated class, because it contains the logic to
    transfer parameters. This is even more complicated, because there may be
    multiple call to functions and recursion has to be avoided.

    TODO InstantElements ?
    """
    cache = {}

    @memoize_default(default=[])
    def get_return_types(self, evaluate_generator=False):
        """
        Get the return vars of a function.
        """
        #a = self.var_args; print '\n\n', a, a.values, a.parent_stmt
        stmts = []
        if isinstance(self.base, Class):
            # there maybe executions of executions
            stmts = [Instance(self.base, self.var_args)]
        elif isinstance(self.base, Generator):
            return Execution(self.base.func).get_return_types(True)
        else:
            # don't do this with exceptions, as usual, because some deeper
            # exceptions could be catched - and I wouldn't know what happened.
            if hasattr(self.base, 'returns'):
                stmts = self._get_function_returns(evaluate_generator)
            else:
                try:
                    # if it is an instance, we try to execute the __call__().
                    call_method = self.base.get_subscope_by_name('__call__')
                except (AttributeError, KeyError):
                    debug.warning("no execution possible", self.base)
                else:
                    exe = Execution(call_method, self.var_args)
                    stmts = exe.get_return_types()

        debug.dbg('exec results:', stmts, self.base, repr(self))

        return strip_imports(stmts)

    def _get_function_returns(self, evaluate_generator):
        func = self.base
        if func.is_generator and not evaluate_generator:
            return [Generator(func)]
        else:
            stmts = []
            for r in self.returns:
                stmts += follow_statement(r)
            return stmts

    @memoize_default(default=[])
    def get_params(self):
        """
        This returns the params for an Execution/Instance and is injected as a
        'hack' into the parsing.Function class.
        This needs to be here, because Instance can have __init__ functions,
        which act the same way as normal functions.
        """
        def gen_param_name_copy(param, keys=[], values=[], array_type=None):
            """
            Create a param with the original scope (of varargs) as parent.
            """
            calls = parsing.Array(parsing.Array.NOARRAY,
                                            self.var_args.parent_stmt)
            calls.values = values
            calls.keys = keys
            calls.type = array_type
            new_param = copy.copy(param)
            new_param.parent = self.var_args.parent_stmt
            new_param._assignment_calls_calculated = True
            new_param._assignment_calls = calls
            name = copy.copy(param.get_name())
            name.parent = new_param
            #print 'insert', i, name, calls.values, value, self.base.params
            return name

        result = []
        start_offset = 0
        #print '\n\nfunc_params', self.base, self.base.parent, self.base
        if isinstance(self.base, InstanceElement):
            # care for self -> just exclude it and add the instance
            start_offset = 1
            self_name = copy.copy(self.base.params[0].get_name())
            self_name.parent = self.base.instance
            result.append(self_name)

        param_dict = {}
        for param in self.base.params:
            param_dict[str(param.get_name())] = param
        # There may be calls, which don't fit all the params, this just ignores
        # it.
        var_arg_iterator = self.get_var_args_iterator()

        non_matching_keys = []
        keys_only = False
        for param in self.base.params[start_offset:]:
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
                keys_only = True

            #debug.warning('Too many arguments given.', value)

            assignments = param.get_assignment_calls().values
            assignment = assignments[0]
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
                else:
                    # just give it the default values (if there's something
                    # there)
                    values = assignments

            # just ignore all the params that are without a key, after one
            # keyword argument was set.
            if not keys_only or assignment[0] == '**':
                result.append(gen_param_name_copy(param, keys=keys,
                                        values=values, array_type=array_type))
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
                            # take the first index
                            if isinstance(key, parsing.Name):
                                name = key
                            else:
                                name = key[0].name
                            yield name, field
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
                self.pushes.append((key, value))

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

    def get_set_vars(self):
        return self.get_defined_names()

    def get_defined_names(self):
        """
        Call the default method with the own instance (self implements all
        the necessary functions). Add also the params.
        """
      #  result = self.get_params() + parsing.Scope._get_set_vars(self)
      #  print '\n\ndef', result, 'par', self, self.parent
      #  print 'set', parsing.Scope._get_set_vars(self)
      #  print 'set', [r.parent for r in parsing.Scope._get_set_vars(self)]
      #  print 'para', [r.parent.parent for r in self.get_params()]
      #  return result
        return self.get_params() + parsing.Scope._get_set_vars(self)

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

    def copy_properties(self, prop):
        # copy all these lists into this local function.
        attr = getattr(self.base, prop)
        objects = []
        for element in attr:
            temp, element.parent = element.parent, None
            copied = copy.deepcopy(element)
            element.parent = temp
            copied.parent = self
            if isinstance(copied, parsing.Function):
                copied = Function.create(copied)
            objects.append(copied)
        return objects

    def __getattr__(self, name):
        if name not in ['indent', 'line_nr', 'imports']:
            raise AttributeError('Tried to access %s. Why?' % name)
        return getattr(self.base, name)

    @property
    @memoize_default()
    def returns(self):
        return self.copy_properties('returns')

    @property
    @memoize_default()
    def statements(self):
        return self.copy_properties('statements')

    @property
    @memoize_default()
    def subscopes(self):
        return self.copy_properties('subscopes')

    def __repr__(self):
        return "<%s of %s>" % \
                (self.__class__.__name__, self.base)


class Generator(object):
    # TODO bring next(iter, default) to work - default works not
    def __init__(self, func):
        super(Generator, self).__init__()
        self.func = func

    def get_defined_names(self):
        """
        Returns a list of names that define a generator, which can return the
        content of a generator.
        """
        names = []
        for n in ['__next__', 'send']:
            # the name for the `next` function
            name = parsing.Name([n], 0, 0, 0)
            name.parent = self
            names.append(name)
        for n in ['close', 'throw']:
            # the name for the `next` function
            name = parsing.Name([n], 0, 0, 0)
            name.parent = None
            names.append(name)
        debug.dbg('generator names', names)
        return names

    @property
    def parent(self):
        return self.func.parent
        #self.execution.get_return_types()

    def __repr__(self):
        return "<%s of %s>" % (self.__class__.__name__, self.func)


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
            if [x for x in index if ':' in x]:
                return [self]
            else:
                # This is indexing only one element, with a fixed index number,
                # otherwise it just ignores the index (e.g. [1+1])
                try:
                    # multiple elements in the array
                    i = index.get_only_subelement().name
                except AttributeError:
                    pass
                else:
                    try:
                        return self.get_exact_index_types(i)
                    except (IndexError, KeyError):
                        pass
        return self.follow_values(values)

    def get_exact_index_types(self, index):
        if self._array.type == parsing.Array.DICT:
            old_index = index
            index = None
            for i, key_elements in enumerate(self._array.keys):
                # because we only want the key to be a string
                if len(key_elements) == 1:
                    try:
                        str_key = key_elements.get_code()
                    except AttributeError:
                        try:
                            str_key = key_elements[0].name
                        except AttributeError:
                            str_key = None
                    if old_index == str_key:
                        index = i
                        break
            if index is None:
                raise KeyError('No key found in dictionary')
        values = [self._array[index]]
        return self.follow_values(values)

    def follow_values(self, values):
        """ helper function for the index getters """
        scope = self._array.parent_stmt.parent
        return follow_call_list(scope, values)

    def get_defined_names(self):
        """
        This method generates all ArrayElements for one parsing.Array.
        It returns e.g. for a list: append, pop, ...
        """
        # array.type is a string with the type, e.g. 'list'
        scope = get_scopes_for_name(builtin.Builtin.scope, self._array.type)[0]
        names = scope.get_defined_names()
        return [ArrayElement(n) for n in names]

    def get_contents(self):
        return self._array

    @property
    def parent(self):
        """
        Return the builtin scope as parent, because the arrays are builtins
        """
        return builtin.Builtin.scope

    def __getattr__(self, name):
        if name not in ['type']:
            raise AttributeError('Strange access: %s.' % name)
        return getattr(self._array, name)

    def __repr__(self):
        return "<e%s of %s>" % (self.__class__.__name__, self._array)


class ArrayElement(object):
    def __init__(self, name):
        super(ArrayElement, self).__init__()
        self.name = name

    def __getattr__(self, name):
        # set access rights:
        if name not in ['parent', 'names', 'line_nr', 'indent']:
            raise AttributeError('Strange access: %s.' % name)
        return getattr(self.name, name)

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
        # `parsing.Class` is used, because the parent is never `Class`.
        # ignore the Flows, because the classes and functions care for that.
        if not (scope != start_scope and isinstance(scope, (parsing.Class))
                or isinstance(scope, parsing.Flow)):
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
                elif isinstance(r, parsing.Function):
                    r = Function.create(r)
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
                # not known. Therefore add a new instance for self. Otherwise
                # take the existing.
                if isinstance(scope, InstanceElement):
                    inst = scope.instance
                else:
                    inst = Instance(Class(par.parent.parent))
                result.append(inst)
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
                    if not name.parent or name.parent.parent == scope:
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
        scope = stmt.get_parent_until(parsing.Function, Function, Execution,
                                        parsing.Class, Instance,
                                        InstanceElement)
    debug.dbg('follow_stmt', stmt, stmt.parent, 'in', scope, seek_name)

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
                    # with things like params, these can also be functions, etc
                    if isinstance(call, (Function, parsing.Class)):
                        result.append(call)
                    elif not isinstance(call, str):
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
        if not isinstance(current, parsing.NamePart):
            if current.type in (parsing.Call.STRING, parsing.Call.NUMBER):
                t = type(current.name).__name__
                scopes = get_scopes_for_name(builtin.Builtin.scope, t)
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

    debug.dbg('call before result %s, current "%s", scope %s'
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
            debug.dbg('exec', scope)
            result = Execution(scope, current).get_return_types()
        else:
            # curly braces are not allowed, because they make no sense
            debug.warning('strange function call with {}', current, scope)
    else:
        if isinstance(scope, Function):
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
