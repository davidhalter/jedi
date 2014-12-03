"""
Contains all classes and functions to deal with lists, dicts, generators and
iterators in general.

Array modifications
*******************

If the content of an array (``set``/``list``) is requested somewhere, the
current module will be checked for appearances of ``arr.append``,
``arr.insert``, etc.  If the ``arr`` name points to an actual array, the
content will be added

This can be really cpu intensive, as you can imagine. Because |jedi| has to
follow **every** ``append`` and check wheter it's the right array. However this
works pretty good, because in *slow* cases, the recursion detector and other
settings will stop this process.

It is important to note that:

1. Array modfications work only in the current module.
2. Jedi only checks Array additions; ``list.pop``, etc are ignored.
"""
from itertools import chain

from jedi import common
from jedi import debug
from jedi import settings
from jedi._compatibility import use_metaclass, is_py3, unicode
from jedi.parser import tree as pr
from jedi.evaluate import compiled
from jedi.evaluate import helpers
from jedi.evaluate import precedence
from jedi.evaluate.cache import CachedMetaClass, memoize_default, NO_DEFAULT
from jedi.cache import underscore_memoization
from jedi.evaluate import analysis


def unite(iterable):
    """Turns a two dimensional array into a one dimensional."""
    return list(chain.from_iterable(iterable))


class IterableWrapper(pr.Base):
    def is_class(self):
        return False


class GeneratorMixin(object):
    @underscore_memoization
    def _get_defined_names(self):
        """
        Returns a list of names that define a generator, which can return the
        content of a generator.
        """
        executes_generator = '__next__', 'send', 'next'
        for name in compiled.generator_obj.get_defined_names():
            if name.name in executes_generator:
                parent = GeneratorMethod(self, name.parent)
                yield helpers.FakeName(name.name, parent)
            else:
                yield name

    def scope_names_generator(self, position=None):
        yield self, self._get_defined_names()

    def get_index_types(self, evaluator, index_array):
        #debug.warning('Tried to get array access on a generator: %s', self)
        analysis.add(self._evaluator, 'type-error-generator', index_array)
        return []

    def get_exact_index_types(self, index):
        """
        Exact lookups are used for tuple lookups, which are perfectly fine if
        used with generators.
        """
        return [self.iter_content()[index]]


class Generator(use_metaclass(CachedMetaClass, IterableWrapper, GeneratorMixin)):
    """Handling of `yield` functions."""
    def __init__(self, evaluator, func, var_args):
        super(Generator, self).__init__()
        self._evaluator = evaluator
        self.func = func
        self.var_args = var_args

    def iter_content(self):
        """ returns the content of __iter__ """
        # Directly execute it, because with a normal call to py__call__ a
        # Generator will be returned.
        from jedi.evaluate.representation import FunctionExecution
        f = FunctionExecution(self._evaluator, self.func, self.var_args)
        return f.get_return_types(check_yields=True)

    def __getattr__(self, name):
        if name not in ['start_pos', 'end_pos', 'parent', 'get_imports',
                        'asserts', 'doc', 'docstr', 'get_parent_until',
                        'get_code', 'subscopes']:
            raise AttributeError("Accessing %s of %s is not allowed."
                                 % (self, name))
        return getattr(self.func, name)

    def __repr__(self):
        return "<%s of %s>" % (type(self).__name__, self.func)


class GeneratorMethod(IterableWrapper):
    """``__next__`` and ``send`` methods."""
    def __init__(self, generator, builtin_func):
        self._builtin_func = builtin_func
        self._generator = generator

    def py__call__(self, evaluator, params):
        # TODO add TypeError if params are given.
        return self._generator.iter_content()

    def __getattr__(self, name):
        return getattr(self._builtin_func, name)


class Comprehension(IterableWrapper):
    @staticmethod
    def from_atom(evaluator, atom):
        mapping = {
            '(': GeneratorComprehension,
            '[': ListComprehension
        }
        return mapping[atom.children[0]](evaluator, atom)

    def __init__(self, evaluator, atom):
        self._evaluator = evaluator
        self._atom = atom

    @memoize_default()
    def eval_node(self):
        """
        The first part `x + 1` of the list comprehension:

            [x + 1 for x in foo]
        """
        comprehension = self._atom.children[1]
        # For nested comprehensions we need to search the last one.
        last = comprehension.children[-1]
        last_comp = comprehension.children[1]
        while True:
            if isinstance(last, pr.CompFor):
                last_comp = last
            elif not pr.is_node(last, 'comp_if'):
                break
            last = last.children[-1]

        return helpers.deep_ast_copy(comprehension.children[0], {comprehension: last_comp})

    def get_exact_index_types(self, index):
        return [self._evaluator.eval_element(self.eval_node())[index]]

    def __repr__(self):
        return "<e%s of %s>" % (type(self).__name__, self._atom)


class ListComprehension(Comprehension):
    def get_index_types(self, evaluator, index):
        return self.iter_content()

    def iter_content(self):
        return self._evaluator.eval_element(self.eval_node())

    @property
    def name(self):
        return FakeSequence(self._evaluator, [], pr.Array.LIST).name


class GeneratorComprehension(Comprehension, GeneratorMixin):
    def iter_content(self):
        return self._evaluator.eval_element(self.eval_node())


class Array(IterableWrapper):
    """
    Used as a mirror to pr.Array, if needed. It defines some getter
    methods which are important in this module.
    """
    mapping = {'(': pr.Array.TUPLE,
               '[': pr.Array.LIST,
               '{': pr.Array.DICT}

    def __init__(self, evaluator, atom):
        self._evaluator = evaluator
        self._atom = atom
        self.type = Array.mapping[atom.children[0]]

        c = self._atom.children
        array_node = c[1]
        if self.type == pr.Array.DICT and array_node != '}' \
                and (not hasattr(array_node, 'children')
                     or ':' not in array_node.children):
            self.type = pr.Array.SET

    @property
    def name(self):
        return helpers.FakeName(self.type, parent=self)

    def py__bool__(self):
        return None  # We don't know the length, because of appends.

    @memoize_default(NO_DEFAULT)
    def get_index_types(self, evaluator, index=()):
        """
        Get the types of a specific index or all, if not given.

        :param index: A subscriptlist node (or subnode).
        """
        indexes = create_indexes_or_slices(evaluator, index)
        lookup_done = False
        types = []
        for index in indexes:
            if isinstance(index, Slice):
                types += [self]
                lookup_done = True
            elif isinstance(index, compiled.CompiledObject) \
                    and isinstance(index.obj, (int, str, unicode)):
                with common.ignored(KeyError, IndexError, TypeError):
                    types += self.get_exact_index_types(index.obj)
                    lookup_done = True

        return types if lookup_done else self.values()

    @memoize_default(NO_DEFAULT)
    def values(self):
        result = unite(self._evaluator.eval_element(v) for v in self._values())
        # TODO reenable
        #result += check_array_additions(self._evaluator, self)
        return result

    def get_exact_index_types(self, mixed_index):
        """ Here the index is an int/str. Raises IndexError/KeyError """
        if self.type == pr.Array.DICT:
            for key, values in self._items():
                # Because we only want the key to be a string.
                keys = self._evaluator.eval_element(key)

                for k in keys:
                    if isinstance(k, compiled.CompiledObject) \
                            and mixed_index == k.obj:
                        for value in values:
                            return self._evaluator.eval_element(value)
            raise KeyError('No key found in dictionary %s.' % self)

        # Can raise an IndexError
        return self._evaluator.eval_element(self._items()[mixed_index])

    def scope_names_generator(self, position=None):
        """
        It returns e.g. for a list: append, pop, ...
        """
        # `array.type` is a string with the type, e.g. 'list'.
        scope = self._evaluator.find_types(compiled.builtin, self.type)[0]
        scope = self._evaluator.execute(scope)[0]  # builtins only have one class
        for _, names in scope.scope_names_generator():
            yield self, names

    @common.safe_property
    def parent(self):
        return compiled.builtin

    def get_parent_until(self):
        return compiled.builtin

    def __getattr__(self, name):
        if name not in ['start_pos', 'get_only_subelement', 'parent',
                        'get_parent_until', 'items']:
            raise AttributeError('Strange access on %s: %s.' % (self, name))
        return getattr(self._atom, name)

    def _values(self):
        """Returns a list of a list of node."""
        if self.type == pr.Array.DICT:
            return list(chain.from_iterable(v for k, v in self._items()))
        else:
            return self._items()

    def _items(self):
        c = self._atom.children
        array_node = c[1]
        if array_node in (']', '}', ')'):
            return []  # Direct closing bracket, doesn't contain items.

        if pr.is_node(array_node, 'testlist_comp'):
            return array_node.children[::2]
        elif pr.is_node(array_node, 'dictorsetmaker'):
            kv = []
            iterator = iter(array_node.children)
            for key in iterator:
                op = next(iterator, None)
                if op is None or op == ',':
                    kv.append(key)  # A set.
                elif op == ':':  # A dict.
                    kv.append((key, [next(iterator)]))
                    next(iterator, None)  # Possible comma.
                else:
                    raise NotImplementedError('dict/set comprehensions')
            return kv
        else:
            return [array_node]

    def __iter__(self):
        return iter(self._items())

    def __repr__(self):
        return "<%s of %s>" % (type(self).__name__, self._atom)


class _FakeArray(Array):
    def __init__(self, evaluator, container, type):
        self.type = type
        self._evaluator = evaluator
        self._atom = container


class ImplicitTuple(_FakeArray):
    def __init__(self, evaluator, testlist):
        super(ImplicitTuple, self).__init__(evaluator, testlist, pr.Array.TUPLE)
        self._testlist = testlist

    def _items(self):
        return self._testlist.children[::2]


class FakeSequence(_FakeArray):
    def __init__(self, evaluator, sequence_values, type):
        super(FakeSequence, self).__init__(evaluator, sequence_values, type)
        self._sequence_values = sequence_values

    def _items(self):
        return self._sequence_values

    def get_exact_index_types(self, index):
        value = self._sequence_values[index]
        return self._evaluator.eval_element(value)


class AlreadyEvaluated(frozenset):
    """A simple container to add already evaluated objects to an array."""
    pass


class MergedNodes(frozenset):
    pass


class FakeDict(_FakeArray):
    def __init__(self, evaluator, dct):
        super(FakeDict, self).__init__(evaluator, dct, pr.Array.DICT)
        self._dct = dct

    def get_exact_index_types(self, index):
        return list(chain.from_iterable(self._evaluator.eval_element(v)
                                        for v in self._dct[index]))

    def _items(self):
        return self._dct.items()


class MergedArray(_FakeArray):
    def __init__(self, evaluator, arrays):
        super(MergedArray, self).__init__(evaluator, arrays, arrays[-1].type)
        self._arrays = arrays

    def get_index_types(self, evaluator, mixed_index):
        return list(chain(*(a.values() for a in self._arrays)))

    def get_exact_index_types(self, mixed_index):
        raise IndexError

    def __iter__(self):
        for array in self._arrays:
            for a in array:
                yield a

    def __len__(self):
        return sum(len(a) for a in self._arrays)


def get_iterator_types(inputs):
    """Returns the types of any iterator (arrays, yields, __iter__, etc)."""
    iterators = []
    # Take the first statement (for has always only
    # one, remember `in`). And follow it.
    for it in inputs:
        if isinstance(it, (Generator, Array, ArrayInstance, Comprehension)):
            iterators.append(it)
        else:
            if not hasattr(it, 'execute_subscope_by_name'):
                debug.warning('iterator/for loop input wrong: %s', it)
                continue
            try:
                iterators += it.execute_subscope_by_name('__iter__')
            except KeyError:
                debug.warning('iterators: No __iter__ method found.')

    result = []
    from jedi.evaluate.representation import Instance
    for it in iterators:
        if isinstance(it, Array):
            # Array is a little bit special, since this is an internal array,
            # but there's also the list builtin, which is another thing.
            result += it.values()
        elif isinstance(it, Instance):
            # __iter__ returned an instance.
            name = '__next__' if is_py3 else 'next'
            try:
                result += it.execute_subscope_by_name(name)
            except KeyError:
                debug.warning('Instance has no __next__ function in %s.', it)
        else:
            # TODO this is not correct, __iter__ can return arbitrary input!
            # Is a generator.
            result += it.iter_content()
    return result


def check_array_additions(evaluator, array):
    """ Just a mapper function for the internal _check_array_additions """
    if not pr.Array.is_type(array._array, pr.Array.LIST, pr.Array.SET):
        # TODO also check for dict updates
        return []

    is_list = array._array.type == 'list'
    current_module = array._array.get_parent_until()
    res = _check_array_additions(evaluator, array, current_module, is_list)
    return res


@memoize_default([], evaluator_is_first_arg=True)
def _check_array_additions(evaluator, compare_array, module, is_list):
    """
    Checks if a `pr.Array` has "add" statements:
    >>> a = [""]
    >>> a.append(1)
    """
    if not settings.dynamic_array_additions or isinstance(module, compiled.CompiledObject):
        return []

    def check_calls(calls, add_name):
        """
        Calls are processed here. The part before the call is searched and
        compared with the original Array.
        """
        result = []
        for c in calls:
            call_path = list(c.generate_call_path())
            call_path_simple = [unicode(n) if isinstance(n, pr.Name) else n
                                for n in call_path]
            separate_index = call_path_simple.index(add_name)
            if add_name == call_path_simple[-1] or separate_index == 0:
                # this means that there is no execution -> [].append
                # or the keyword is at the start -> append()
                continue
            backtrack_path = iter(call_path[:separate_index])

            position = c.start_pos
            scope = c.get_parent_scope()

            found = evaluator.eval_call_path(backtrack_path, scope, position)
            if not compare_array in found:
                continue

            params = call_path[separate_index + 1]
            if not params.values:
                continue  # no params: just ignore it
            if add_name in ['append', 'add']:
                for param in params:
                    result += evaluator.eval_statement(param)
            elif add_name in ['insert']:
                try:
                    second_param = params[1]
                except IndexError:
                    continue
                else:
                    result += evaluator.eval_statement(second_param)
            elif add_name in ['extend', 'update']:
                for param in params:
                    iterators = evaluator.eval_statement(param)
                result += get_iterator_types(iterators)
        return result

    from jedi.evaluate import representation as er

    def get_execution_parent(element, *stop_classes):
        """ Used to get an Instance/FunctionExecution parent """
        if isinstance(element, Array):
            stmt = element._array.parent
        else:
            # is an Instance with an ArrayInstance inside
            stmt = element.var_args[0].var_args.parent
        if isinstance(stmt, er.InstanceElement):
            stop_classes = list(stop_classes) + [er.Function]
        return stmt.get_parent_until(stop_classes)

    temp_param_add = settings.dynamic_params_for_other_modules
    settings.dynamic_params_for_other_modules = False

    search_names = ['append', 'extend', 'insert'] if is_list else \
        ['add', 'update']
    comp_arr_parent = get_execution_parent(compare_array, er.FunctionExecution)

    possible_stmts = []
    res = []
    for n in search_names:
        try:
            possible_stmts += module.used_names[n]
        except KeyError:
            continue
        for stmt in possible_stmts:
            # Check if the original scope is an execution. If it is, one
            # can search for the same statement, that is in the module
            # dict. Executions are somewhat special in jedi, since they
            # literally copy the contents of a function.
            if isinstance(comp_arr_parent, er.FunctionExecution):
                stmt = comp_arr_parent. \
                    get_statement_for_position(stmt.start_pos)
                if stmt is None:
                    continue
            # InstanceElements are special, because they don't get copied,
            # but have this wrapper around them.
            if isinstance(comp_arr_parent, er.InstanceElement):
                stmt = er.get_instance_el(comp_arr_parent.instance, stmt)

            if evaluator.recursion_detector.push_stmt(stmt):
                # check recursion
                continue

            res += check_calls(helpers.scan_statement_for_calls(stmt, n), n)
            evaluator.recursion_detector.pop_stmt()
    # reset settings
    settings.dynamic_params_for_other_modules = temp_param_add
    return res


def check_array_instances(evaluator, instance):
    """Used for set() and list() instances."""
    
    return instance.var_args


    if not settings.dynamic_arrays_instances:
        return instance.var_args
    ai = ArrayInstance(evaluator, instance)
    return [ai]


class ArrayInstance(IterableWrapper):
    """
    Used for the usage of set() and list().
    This is definitely a hack, but a good one :-)
    It makes it possible to use set/list conversions.
    """
    def __init__(self, evaluator, instance):
        self._evaluator = evaluator
        self.instance = instance
        self.var_args = instance.var_args

    def iter_content(self):
        """
        The index is here just ignored, because of all the appends, etc.
        lists/sets are too complicated too handle that.
        """
        items = []
        from jedi.evaluate.representation import Instance
        for stmt in self.var_args:
            for typ in self._evaluator.eval_statement(stmt):
                if isinstance(typ, Instance) and len(typ.var_args):
                    array = typ.var_args[0]
                    if isinstance(array, ArrayInstance):
                        # Certain combinations can cause recursions, see tests.
                        if not self._evaluator.recursion_detector.push_stmt(self.var_args):
                            items += array.iter_content()
                            self._evaluator.recursion_detector.pop_stmt()
                items += get_iterator_types([typ])

        # TODO check if exclusion of tuple is a problem here.
        if isinstance(self.var_args, tuple) or self.var_args.parent is None:
            return []  # generated var_args should not be checked for arrays

        module = self.var_args.get_parent_until()
        is_list = str(self.instance.name) == 'list'
        items += _check_array_additions(self._evaluator, self.instance, module, is_list)
        return items


class Slice(object):
    def __init__(self, evaluator, start, stop, step):
        self._evaluator = evaluator
        # all of them are either a Precedence or None.
        self._start = start
        self._stop = stop
        self._step = step

    @property
    def obj(self):
        """
        Imitate CompiledObject.obj behavior and return a ``builtin.slice()``
        object.
        """
        def get(element):
            if element is None:
                return None

            result = precedence.process_precedence_element(self._evaluator, element)
            if len(result) != 1:
                # We want slices to be clear defined with just one type.
                # Otherwise we will return an empty slice object.
                raise IndexError
            try:
                return result[0].obj
            except AttributeError:
                return None

        try:
            return slice(get(self._start), get(self._stop), get(self._step))
        except IndexError:
            return slice(None, None, None)


def create_indexes_or_slices(evaluator, index):
    if pr.is_node(index, 'subscript'):  # subscript is a slice operation.
        start, stop, step = None, None, None
        result = []
        for el in index.children:
            if el == ':' and not result:
                result.append(None)
            elif pr.is_node(el, 'sliceop'):
                if len(el.children) == 2:
                    result.append(el.children[1])
            else:
                result.append(result)
        result += [None] * (3 - len(result))

        return (Slice(evaluator, *result),)
    return evaluator.eval_element(index)
    # TODO delete the rest?


    # Just take the first part of the "array", because this is Python stdlib
    # behavior. Numpy et al. perform differently, but Jedi won't understand
    # that anyway.
    expression_list = index[0].expression_list()
    prec = precedence.create_precedence(expression_list)

    # check for slices
    if isinstance(prec, precedence.Precedence) and prec.operator == ':':
        start = prec.left
        if isinstance(start, precedence.Precedence) and start.operator == ':':
            stop = start.right
            start = start.left
            step = prec.right
        else:
            stop = prec.right
            step = None
        return (Slice(evaluator, start, stop, step),)
    else:
        return tuple(precedence.process_precedence_element(evaluator, prec))
