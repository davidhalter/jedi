"""
follow_statement -> follow_call -> follow_paths -> follow_path
'follow_import'

`get_names_for_scope` and `get_scopes_for_name` are search functions

TODO doc
TODO list comprehensions, priority? +1
TODO magic methods: __mul__, __add__, etc.
TODO evaluate asserts (type safety)

python 3 stuff:
TODO class decorators
TODO annotations ? how ? type evaluation and return?
TODO nonlocal statement

TODO getattr / __getattr__ / __getattribute__ ?

TODO descriptors (also for classes, for instances it should work)
TODO @staticmethod @classmethod (implement descriptors, builtins are done)
TODO variable assignments in classes (see test/completion/classes @230) +1
"""
from _compatibility import next, property, hasattr
import sys

import itertools
import copy

import parsing
import debug
import builtin
import imports
import helpers

memoize_caches = []


class DecoratorNotFound(LookupError):
    """
    Decorators are sometimes not found, if that happens, that error is raised.
    """
    pass


class MultiLevelStopIteration(Exception):
    """
    StopIteration's get catched pretty easy by for loops, let errors propagate.
    """
    pass


class MultiLevelAttributeError(BaseException):
    """
    Important, because `__getattr__` and `hasattr` catch AttributeErrors
    implicitly. This is really evil (mainly because of `__getattr__`).
    `hasattr` in Python 2 is even more evil, because it catches ALL exceptions.
    Therefore this class has to be `BaseException` and not `Exception`.

    :param base: return values of sys.exc_info().
    """
    def __init__(self, base):
        self.base = base

    def __str__(self):
        import traceback
        tb = traceback.format_exception(*self.base)
        return 'Original:\n\n' + ''.join(tb)


def clear_caches():
    for m in memoize_caches:
        m.clear()

    follow_statement.reset()


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


class CachedMetaClass(type):
    """
    This is basically almost the same than the decorator above, it just caches
    class initializations. I haven't found any other way, so I do it with meta
    classes.
    """
    @memoize_default()
    def __call__(self, *args, **kwargs):
        return super(CachedMetaClass, self).__call__(*args, **kwargs)


class Executable(object):
    """ An instance is also an executable - because __init__ is called """
    def __init__(self, base, var_args=parsing.Array(None, None)):
        self.base = base
        # The param input array.
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
            instance_el = InstanceElement(self, Function(func))
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

    def get_self_properties(self):
        def add_self_name(name):
            n = copy.copy(name)
            n.names = n.names[1:]
            names.append(InstanceElement(self, n))

        names = []
        # This loop adds the names of the self object, copies them and removes
        # the self.
        for sub in self.base.subscopes:
            if isinstance(sub, parsing.Class):
                continue
            # Get the self name, if there's one.
            self_name = self.get_func_self_name(sub)
            if self_name:
                # Check the __init__ function.
                if self.var_args and sub.name.get_code() == '__init__':
                    sub = self.get_init_execution(sub)
                for n in sub.get_set_vars():
                    # Only names with the selfname are being added.
                    # It is also important, that they have a len() of 2,
                    # because otherwise, they are just something else
                    if n.names[0] == self_name and len(n.names) == 2:
                        add_self_name(n)

        for s in self.base.get_super_classes():
            names += Instance(s).get_self_properties()

        return names

    def get_defined_names(self):
        """
        Get the instance vars of a class. This includes the vars of all
        classes
        """
        names = self.get_self_properties()

        class_names = self.base.get_defined_names()
        for var in class_names:
            # Functions are also instance elements.
            if isinstance(var.parent, (Function, parsing.Function)):
                var = InstanceElement(self, var)
            names.append(var)
        return names

    def get_descriptor_return(self, obj):
        """ Throws an error if there's no method. """
        method = self.get_subscope_by_name('__get__')
        # Arguments in __set__ descriptors are obj, class.
        # `method` is the new parent of the array, don't know if that's good.
        args = parsing.Array('tuple', method, values=[[obj], [obj.base]])
        method = InstanceElement(self, method)
        res = Execution(method, args).get_return_types()

        return res

    def __getattr__(self, name):
        if name == 'get_index_types':
            # TODO Call __getitem__ in such cases?
            return lambda: []
        if name not in ['start_pos', 'end_pos', 'name', 'get_imports']:
            raise AttributeError("Instance %s: Don't touch this (%s)!"
                                    % (self, name))
        return getattr(self.base, name)

    def __repr__(self):
        return "<e%s of %s (var_args: %s)>" % \
                (self.__class__.__name__, self.base, len(self.var_args or []))


class InstanceElement(object):
    def __init__(self, instance, var):
        super(InstanceElement, self).__init__()
        self.instance = instance
        self.var = var

    @property
    @memoize_default()
    def parent(self):
        par = self.var.parent
        if isinstance(par, parsing.Function):
            par = Function(par)
        if not isinstance(par, parsing.Module):
            par = InstanceElement(self.instance, par)
        return par

    def get_parent_until(self, *classes):
        scope = self.var.get_parent_until(*classes)
        return InstanceElement(self.instance, scope)

    def get_assignment_calls(self):
        # Copy and modify the array.
        origin = self.var.get_assignment_calls()
        origin.parent_stmt, temp = None, origin.parent_stmt
        # Delete parent, because it isn't used anymore.
        new = helpers.fast_parent_copy(origin)
        origin.parent_stmt = temp
        new.parent_stmt = InstanceElement(self.instance, temp)
        return new

    def __getattr__(self, name):
        return getattr(self.var, name)

    def __repr__(self):
        return "<%s of %s>" % (self.__class__.__name__, self.var)


class Class(object):
    __metaclass__ = CachedMetaClass

    def __init__(self, base):
        self.base = base

    @memoize_default(default=[])
    def get_super_classes(self):
        supers = []
        # TODO care for mro stuff (multiple super classes).
        for s in self.base.supers:
            # Super classes are statements.
            for cls in follow_statement(s):
                if not isinstance(cls, Class):
                    debug.warning('Received non class, as a super class')
                    continue  # Just ignore other stuff (user input error).
                supers.append(cls)
        return supers

    @memoize_default(default=[])
    def get_defined_names(self):
        def in_iterable(name, iterable):
            """ checks if the name is in the variable 'iterable'. """
            for i in iterable:
                # Only the last name is important, because these names have a
                # maximal length of 2, with the first one being `self`.
                if i.names[-1] == name.names[-1]:
                    return True
            return False

        result = self.base.get_defined_names()
        super_result = []
        for cls in self.get_super_classes():
            # Get the inherited names.
            for i in cls.get_defined_names():
                if not in_iterable(i, result):
                    super_result.append(i)
        result += super_result
        return result

    @property
    def name(self):
        return self.base.name

    def __getattr__(self, name):
        if name not in ['start_pos', 'end_pos', 'parent', 'subscopes',
                            'get_imports']:
            raise AttributeError("Don't touch this (%s)!" % name)
        return getattr(self.base, name)

    def __repr__(self):
        return "<e%s of %s>" % (self.__class__.__name__, self.base)


class Function(object):
    """
    """
    __metaclass__ = CachedMetaClass

    def __init__(self, func, is_decorated=False):
        """ This should not be called directly """
        self.base_func = func
        self.is_decorated = is_decorated

    @property
    @memoize_default()
    def decorated_func(self):
        """
        Returns the function, that is to be executed in the end.
        This is also the places where the decorators are processed.
        """
        f = self.base_func

        # Only enter it, if has not already been processed.
        if not self.is_decorated:
            for dec in reversed(self.base_func.decorators):
                debug.dbg('decorator:', dec, f)
                dec_results = follow_statement(dec)
                if not len(dec_results):
                    debug.warning('decorator func not found: %s in stmt %s' %
                                                        (self.base_func, dec))
                    return None
                if len(dec_results) > 1:
                    debug.warning('multiple decorators found', self.base_func,
                                                            dec_results)
                decorator = dec_results.pop()
                # Create param array.
                old_func = Function(f, is_decorated=True)
                params = parsing.Array(parsing.Array.NOARRAY, old_func)
                params.values = [[old_func]]

                wrappers = Execution(decorator, params).get_return_types()
                if not len(wrappers):
                    debug.warning('no wrappers found', self.base_func)
                    return None
                if len(wrappers) > 1:
                    debug.warning('multiple wrappers found', self.base_func,
                                                                wrappers)
                # This is here, that the wrapper gets executed.
                f = wrappers[0]

                debug.dbg('decorator end', f)
        if f != self.base_func and isinstance(f, parsing.Function):
            f = Function(f)
        return f

    def __getattr__(self, name):
        if self.decorated_func == None:
            raise DecoratorNotFound('Accessed name %s in function' % name)
        return getattr(self.decorated_func, name)

    def __repr__(self):
        dec = ''
        if self.decorated_func != self.base_func:
            dec = " is " + repr(self.decorated_func)
        return "<e%s of %s%s>" % (self.__class__.__name__, self.base_func, dec)


class Execution(Executable):
    """
    This class is used to evaluate functions and their returns.

    This is the most complicated class, because it contains the logic to
    transfer parameters. This is even more complicated, because there may be
    multiple call to functions and recursion has to be avoided.
    """
    cache = {}

    @memoize_default(default=[])
    def get_return_types(self, evaluate_generator=False):
        """
        Get the return vars of a function.
        """
        stmts = []
        if isinstance(self.base, Class):
            # There maybe executions of executions.
            stmts = [Instance(self.base, self.var_args)]
        elif isinstance(self.base, Generator):
            return self.base.execute()
        else:
            # Don't do this with exceptions, as usual, because some deeper
            # exceptions could be catched - and I wouldn't know what happened.
            try:
                self.base.returns
            except (AttributeError, DecoratorNotFound):
                try:
                    # If it is an instance, we try to execute the __call__().
                    call_method = self.base.get_subscope_by_name('__call__')
                except (AttributeError, KeyError, DecoratorNotFound):
                    debug.warning("no execution possible", self.base)
                else:
                    debug.dbg('__call__', call_method, self.base)
                    base = self.base
                    if isinstance(self.base, Function):
                        base = self.base.decorated_func
                    call_method = InstanceElement(base, call_method)
                    exe = Execution(call_method, self.var_args)
                    stmts = exe.get_return_types()
            else:
                stmts = self._get_function_returns(evaluate_generator)

        debug.dbg('exec result: %s in %s' % (stmts, self))

        return imports.strip_imports(stmts)

    def _get_function_returns(self, evaluate_generator):
        func = self.base
        if func.is_generator and not evaluate_generator:
            return [Generator(func, self.var_args)]
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
            parent_stmt = self.var_args.parent_stmt
            calls = parsing.Array(parsing.Array.NOARRAY, parent_stmt)
            calls.values = values
            calls.keys = keys
            calls.type = array_type
            new_param = copy.copy(param)
            new_param.parent = parent_stmt
            new_param._assignment_calls_calculated = True
            new_param._assignment_calls = calls
            name = copy.copy(param.get_name())
            name.parent = new_param
            return name

        result = []
        start_offset = 0
        if isinstance(self.base, InstanceElement):
            # Care for self -> just exclude it and add the instance
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
            # Wrong value count is just ignored. If you try to test cases which
            # are not allowed in Python, Jedi will maybe not show any
            # completions.
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
                    # Iterate until a key argument is found.
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
                    # No value: return the default values.
                    values = assignments

            # Just ignore all the params that are without a key, after one
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
            # `var_args` is typically an Array, and not a list.
            for var_arg in self.var_args:
                # *args
                if var_arg[0] == '*':
                    arrays = follow_call_list([var_arg[1:]])
                    for array in arrays:
                        for field in array.get_contents():
                            yield None, field
                # **kwargs
                elif var_arg[0] == '**':
                    arrays = follow_call_list([var_arg[1:]])
                    for array in arrays:
                        for key, field in array.get_contents():
                            # Take the first index.
                            if isinstance(key, parsing.Name):
                                name = key
                            else:
                                # `parsing`.[Call|Function|Class] lookup.
                                name = key[0].name
                            yield name, field
                # Normal arguments (including key arguments).
                else:
                    if len(var_arg) > 1 and var_arg[1] == '=':
                        # This is a named parameter (var_arg[0] is a Call).
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
        return self.get_params() + parsing.Scope._get_set_vars(self)

    def copy_properties(self, prop):
        # Copy all these lists into this local function.
        attr = getattr(self.base, prop)
        objects = []
        for element in attr:
            temp, element.parent = element.parent, None
            copied = copy.deepcopy(element)
            element.parent = temp
            copied.parent = self
            if isinstance(copied, parsing.Function):
                copied = Function(copied)
            objects.append(copied)
        return objects

    def __getattr__(self, name):
        if name not in ['start_pos', 'end_pos', 'imports']:
            raise AttributeError('Tried to access %s: %s. Why?' % (name, self))
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
    def __init__(self, func, var_args):
        super(Generator, self).__init__()
        self.func = func
        self.var_args = var_args

    def get_defined_names(self):
        """
        Returns a list of names that define a generator, which can return the
        content of a generator.
        """
        names = []
        none_pos = (0, 0)
        executes_generator = ('__next__', 'send')
        for n in ('close', 'throw') + executes_generator:
            name = parsing.Name([n], none_pos, none_pos)
            if n in executes_generator:
                name.parent = self
            else:
                name.parent = None
            names.append(name)
        debug.dbg('generator names', names)
        return names

    def execute(self):
        return Execution(self.func, self.var_args).get_return_types(True)

    @property
    def parent(self):
        return self.func.parent

    def get_index_types(self, index=None):
        # TODO check if this method is right here, this means that Generators
        # can be indexed, which is not the Python way.
        return self.execute()

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
                # otherwise it just ignores the index (e.g. [1+1]).
                try:
                    # Multiple elements in the array.
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
                # Because we only want the key to be a string.
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
        return follow_call_list(values)

    def get_defined_names(self):
        """
        This method generates all ArrayElements for one parsing.Array.
        It returns e.g. for a list: append, pop, ...
        """
        # `array.type` is a string with the type, e.g. 'list'.
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
        # Set access privileges:
        if name not in ['parent', 'names', 'start_pos', 'end_pos']:
            raise AttributeError('Strange access: %s.' % name)
        return getattr(self.name, name)

    def __repr__(self):
        return "<%s of %s>" % (self.__class__.__name__, self.name)


def get_defined_names_for_position(obj, position=None, start_scope=None):
    """
    :param position: the position as a line/column tuple, default is infinity.
    """
    names = obj.get_defined_names()
    # Instances have special rules, always return all the possible completions,
    # because class variables are always valid and the `self.` variables, too.
    if not position or isinstance(obj, Instance) or isinstance(obj, Function) \
                            and isinstance(obj.decorated_func, Instance) \
                or start_scope != obj and isinstance(start_scope,
                                            (parsing.Function, Execution)):
        return names
    names_new = []
    for n in names:
        if (n.start_pos) < position:
            names_new.append(n)
    return names_new


def get_names_for_scope(scope, position=None, star_search=True,
                                                        include_builtin=True):
    """
    Get all completions possible for the current scope.
    The star search option is only here to provide an optimization. Otherwise
    the whole thing would probably start a little recursive madness.
    """
    start_scope = scope
    while scope:
        # `parsing.Class` is used, because the parent is never `Class`.
        # Ignore the Flows, because the classes and functions care for that.
        if not (scope != start_scope and isinstance(scope, parsing.Class)
                or isinstance(scope, parsing.Flow)
                or isinstance(scope, InstanceElement)
                and isinstance(scope.var, parsing.Class)):
            try:
                yield scope, get_defined_names_for_position(scope, position,
                                                                start_scope)
            except StopIteration:
                raise MultiLevelStopIteration('StopIteration raised somewhere')
        scope = scope.parent

    # Add star imports.
    if star_search:
        for s in imports.remove_star_imports(start_scope.get_parent_until()):
            for g in get_names_for_scope(s, star_search=False):
                yield g

        # Add builtins to the global scope.
        if include_builtin:
            builtin_scope = builtin.Builtin.scope
            yield builtin_scope, builtin_scope.get_defined_names()


def get_scopes_for_name(scope, name_str, position=None, search_global=False):
    """
    :param position: Position of the last statement -> tuple of line, column
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
                # Global variables handling.
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
                    r = Function(r)
                res_new.append(r)
        debug.dbg('sfn remove, new: %s, old: %s' % (res_new, result))
        return res_new

    def filter_name(scope_generator):
        def handle_non_arrays(name):
            result = []
            par = name.parent
            if isinstance(par, parsing.Flow):
                if par.command == 'for':
                    # Take the first statement (for has always only
                    # one, remember `in`). And follow it. After that,
                    # get the types which are in the array.
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
                # This is where self gets added - this happens at another
                # place, if the var_args are clear. But sometimes the class is
                # not known. Therefore add a new instance for self. Otherwise
                # take the existing.
                if isinstance(scope, InstanceElement):
                    inst = scope.instance
                else:
                    inst = Instance(Class(par.parent.parent))
                result.append(inst)
            elif isinstance(par, (InstanceElement)) \
                                and hasattr(par, 'get_descriptor_return'):
                try:
                    result += par.get_descriptor_return(scope)
                except KeyError:
                    result.append(par)
            else:
                result.append(par)
            return result

        result = []
        # compare func uses the tuple of line/indent = line/column
        comparison_func = lambda name: (name.start_pos)
        for scope, name_list in scope_generator:
            break_scopes = []
            # here is the position stuff happening (sorting of variables)
            for name in sorted(name_list, key=comparison_func, reverse=True):
                try:
                    p = name.parent.parent if name.parent else None
                except DecoratorNotFound:
                    debug.warning('catched DecoratorNotFound: %s in %s' \
                                                            % (name, scope))
                    continue
                if name_str == name.get_code() and p not in break_scopes:
                    result += handle_non_arrays(name)
                    # for comparison we need the raw class
                    s = scope.base if isinstance(scope, Class) else scope
                    # this means that a definition was found and is not e.g.
                    # in if/else.
                    if not name.parent or p == s:
                        break
                    break_scopes.append(p)
            # if there are results, ignore the other scopes
            if result:
                break
        debug.dbg('sfn filter "%s" in %s: %s' % (name_str, scope, result))
        return result

    if search_global:
        scope_generator = get_names_for_scope(scope, position=position)
    else:
        names = get_defined_names_for_position(scope, position)
        scope_generator = iter([(scope, names)])

    return remove_statements(filter_name(scope_generator))


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
                try:
                    types += r.get_exact_index_types(index)
                except IndexError:
                    pass
            else:
                debug.warning("invalid tuple lookup %s of result %s in %s"
                                    % (tup, results, seek_name))

        return types

    result = []
    if tup.type == parsing.Array.NOARRAY:
        # Here we have unnessecary braces, which we just remove.
        arr = tup.get_only_subelement()
        result = assign_tuples(arr, results, seek_name)
    else:
        for i, t in enumerate(tup):
            # Used in assignments. There is just one call and no other things,
            # therefore we can just assume, that the first part is important.
            if len(t) != 1:
                raise AttributeError('Array length should be 1')
            t = t[0]

            # Check the left part, if there are still tuples in it or a Call.
            if isinstance(t, parsing.Array):
                # These are "sub"-tuples.
                result += assign_tuples(t, eval_results(i), seek_name)
            else:
                if t.name.names[-1] == seek_name:
                    result += eval_results(i)
    return result


@helpers.RecursionDecorator
@memoize_default(default=[])
def follow_statement(stmt, seek_name=None):
    """
    :param stmt: contains a statement
    :param scope: contains a scope. If not given, takes the parent of stmt.
    """
    debug.dbg('follow_stmt %s (%s)' % (stmt, seek_name))
    call_list = stmt.get_assignment_calls()
    debug.dbg('calls: %s' % call_list)

    try:
        result = follow_call_list(call_list)
    except AttributeError:
        # This is so evil! But necessary to propagate errors. The attribute
        # errors here must not be catched, because they shouldn't exist.
        raise MultiLevelAttributeError(sys.exc_info())

    # Assignment checking is only important if the statement defines multiple
    # variables.
    if len(stmt.get_set_vars()) > 1 and seek_name and stmt.assignment_details:
        # TODO This should have its own call_list, because call_list can also
        # return 3 results for 2 variables.
        new_result = []
        for op, set_vars in stmt.assignment_details:
            new_result += assign_tuples(set_vars, result, seek_name)
        result = new_result
    return set(result)


def follow_call_list(call_list):
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
        result = follow_call(call_list)
    else:
        result = []
        for calls in call_list:
            calls_iterator = iter(calls)
            for call in calls_iterator:
                if parsing.Array.is_type(call, parsing.Array.NOARRAY):
                    result += follow_call_list(call)
                else:
                    # With things like params, these can also be functions...
                    if isinstance(call, (Function, parsing.Class, Instance)):
                        result.append(call)
                    # The string tokens are just operations (+, -, etc.)
                    elif not isinstance(call, str):
                        # Ternary operators.
                        #if str(call.name) == 'for':  <--- list comprehensions
                        #    print '\n\ndini mueter'
                        if str(call.name) == 'if':
                            while True:
                                call = next(calls_iterator)
                                try:
                                    if str(call.name) == 'else':
                                        break
                                except AttributeError:
                                    pass
                            continue
                        result += follow_call(call)
    return set(result)


def follow_call(call):
    """ Follow a call is following a function, variable, string, etc. """
    scope = call.parent_stmt.parent
    path = call.generate_call_list()

    position = call.parent_stmt.start_pos
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
                scopes = []
            # Make instances of those number/string objects.
            scopes = [Instance(s) for s in scopes]
        else:
            # This is the first global lookup.
            scopes = get_scopes_for_name(scope, current, position=position,
                                            search_global=True)
        result = imports.strip_imports(scopes)

        if result != scopes:
            # Reset the position, when imports where stripped.
            position = None

    debug.dbg('before next follow %s, current "%s", scope %s'
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
                # This means stop iteration.
                return results
    return results_new


def follow_path(path, scope, position=None):
    """
    Takes a generator and tries to complete the path.
    """
    # Current is either an Array or a Scope.
    try:
        current = next(path)
    except StopIteration:
        return None
    debug.dbg('follow %s in scope %s' % (current, scope))

    result = []
    if isinstance(current, parsing.Array):
        # This must be an execution, either () or [].
        if current.type == parsing.Array.LIST:
            result = scope.get_index_types(current)
        elif current.type not in [parsing.Array.DICT]:
            # Scope must be a class or func - make an instance or execution.
            debug.dbg('exe', scope)
            result = Execution(scope, current).get_return_types()
        else:
            # Curly braces are not allowed, because they make no sense.
            debug.warning('strange function call with {}', current, scope)
    else:
        # The function must not be decorated with something else.
        if isinstance(scope, Function) and \
                            isinstance(scope.decorated_func, Function):
            # TODO Check default function methods and return them.
            result = []
        else:
            # TODO Check magic class methods and return them also.
            # This is the typical lookup while chaining things.
            result = imports.strip_imports(get_scopes_for_name(scope, current,
                                                        position=position))
    return follow_paths(path, result, position=position)


