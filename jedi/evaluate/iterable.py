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
from jedi import debug
from jedi import settings
from jedi import common
from jedi.common import unite, safe_property
from jedi._compatibility import unicode, zip_longest, is_py3
from jedi.evaluate import compiled
from jedi.evaluate import helpers
from jedi.evaluate import analysis
from jedi.evaluate import pep0484
from jedi.evaluate import context
from jedi.evaluate import precedence
from jedi.evaluate import recursion
from jedi.evaluate.cache import memoize_default
from jedi.evaluate.filters import DictFilter, AbstractNameDefinition, \
    ParserTreeFilter


class AbstractSequence(context.Context):
    builtin_methods = {}
    api_type = 'instance'

    def __init__(self, evaluator):
        super(AbstractSequence, self).__init__(evaluator, evaluator.BUILTINS)

    def get_filters(self, search_global, until_position=None, origin_scope=None):
        raise NotImplementedError

    @property
    def name(self):
        return compiled.CompiledContextName(self, self.array_type)


class BuiltinMethod(object):
    """``Generator.__next__`` ``dict.values`` methods and so on."""
    def __init__(self, builtin_context, method, builtin_func):
        self._builtin_context = builtin_context
        self._method = method
        self._builtin_func = builtin_func

    def py__call__(self, params):
        return self._method(self._builtin_context)

    def __getattr__(self, name):
        return getattr(self._builtin_func, name)


class SpecialMethodFilter(DictFilter):
    """
    A filter for methods that are defined in this module on the corresponding
    classes like Generator (for __next__, etc).
    """
    class SpecialMethodName(AbstractNameDefinition):
        api_type = 'function'

        def __init__(self, parent_context, string_name, callable_, builtin_context):
            self.parent_context = parent_context
            self.string_name = string_name
            self._callable = callable_
            self._builtin_context = builtin_context

        def infer(self):
            filter = next(self._builtin_context.get_filters())
            # We can take the first index, because on builtin methods there's
            # always only going to be one name. The same is true for the
            # inferred values.
            builtin_func = next(iter(filter.get(self.string_name)[0].infer()))
            return set([BuiltinMethod(self.parent_context, self._callable, builtin_func)])

    def __init__(self, context, dct, builtin_context):
        super(SpecialMethodFilter, self).__init__(dct)
        self.context = context
        self._builtin_context = builtin_context
        """
        This context is what will be used to introspect the name, where as the
        other context will be used to execute the function.

        We distinguish, because we have to.
        """

    def _convert(self, name, value):
        return self.SpecialMethodName(self.context, name, value, self._builtin_context)


def has_builtin_methods(cls):
    base_dct = {}
    # Need to care properly about inheritance. Builtin Methods should not get
    # lost, just because they are not mentioned in a class.
    for base_cls in reversed(cls.__bases__):
        try:
            base_dct.update(base_cls.builtin_methods)
        except AttributeError:
            pass

    cls.builtin_methods = base_dct
    for func in cls.__dict__.values():
        try:
            cls.builtin_methods.update(func.registered_builtin_methods)
        except AttributeError:
            pass
    return cls


def register_builtin_method(method_name, python_version_match=None):
    def wrapper(func):
        if python_version_match and python_version_match != 2 + int(is_py3):
            # Some functions do only apply to certain versions.
            return func
        dct = func.__dict__.setdefault('registered_builtin_methods', {})
        dct[method_name] = func
        return func
    return wrapper


@has_builtin_methods
class GeneratorMixin(object):
    array_type = None

    @register_builtin_method('send')
    @register_builtin_method('next', python_version_match=2)
    @register_builtin_method('__next__', python_version_match=3)
    def py__next__(self):
        # TODO add TypeError if params are given.
        return unite(lazy_context.infer() for lazy_context in self.py__iter__())

    def get_filters(self, search_global, until_position=None, origin_scope=None):
        gen_obj = compiled.get_special_object(self.evaluator, 'GENERATOR_OBJECT')
        yield SpecialMethodFilter(self, self.builtin_methods, gen_obj)
        for filter in gen_obj.get_filters(search_global):
            yield filter

    def py__bool__(self):
        return True

    def py__class__(self):
        gen_obj = compiled.get_special_object(self.evaluator, 'GENERATOR_OBJECT')
        return gen_obj.py__class__()

    @property
    def name(self):
        return compiled.CompiledContextName(self, 'generator')


class Generator(GeneratorMixin, context.Context):
    """Handling of `yield` functions."""

    def __init__(self, evaluator, func_execution_context):
        super(Generator, self).__init__(evaluator, parent_context=evaluator.BUILTINS)
        self._func_execution_context = func_execution_context

    def py__iter__(self):
        return self._func_execution_context.get_yield_values()

    def __repr__(self):
        return "<%s of %s>" % (type(self).__name__, self._func_execution_context)


class CompForContext(context.TreeContext):
    @classmethod
    def from_comp_for(cls, parent_context, comp_for):
        return cls(parent_context.evaluator, parent_context, comp_for)

    def __init__(self, evaluator, parent_context, comp_for):
        super(CompForContext, self).__init__(evaluator, parent_context)
        self.tree_node = comp_for

    def get_node(self):
        return self.tree_node

    def get_filters(self, search_global, until_position=None, origin_scope=None):
        yield ParserTreeFilter(self.evaluator, self)


class Comprehension(AbstractSequence):
    @staticmethod
    def from_atom(evaluator, context, atom):
        bracket = atom.children[0]
        if bracket == '{':
            if atom.children[1].children[1] == ':':
                cls = DictComprehension
            else:
                cls = SetComprehension
        elif bracket == '(':
            cls = GeneratorComprehension
        elif bracket == '[':
            cls = ListComprehension
        return cls(evaluator, context, atom)

    def __init__(self, evaluator, defining_context, atom):
        super(Comprehension, self).__init__(evaluator)
        self._defining_context = defining_context
        self._atom = atom

    def _get_comprehension(self):
        # The atom contains a testlist_comp
        return self._atom.children[1]

    def _get_comp_for(self):
        # The atom contains a testlist_comp
        return self._get_comprehension().children[1]

    def _eval_node(self, index=0):
        """
        The first part `x + 1` of the list comprehension:

            [x + 1 for x in foo]
        """
        return self._get_comprehension().children[index]

    @memoize_default()
    def _get_comp_for_context(self, parent_context, comp_for):
        # TODO shouldn't this be part of create_context?
        return CompForContext.from_comp_for(parent_context, comp_for)

    def _nested(self, comp_fors, parent_context=None):
        evaluator = self.evaluator
        comp_for = comp_fors[0]
        input_node = comp_for.children[3]
        parent_context = parent_context or self._defining_context
        input_types = parent_context.eval_node(input_node)

        iterated = py__iter__(evaluator, input_types, input_node)
        exprlist = comp_for.children[1]
        for i, lazy_context in enumerate(iterated):
            types = lazy_context.infer()
            dct = unpack_tuple_to_dict(evaluator, types, exprlist)
            context = self._get_comp_for_context(
                parent_context,
                comp_for,
            )
            with helpers.predefine_names(context, comp_for, dct):
                try:
                    for result in self._nested(comp_fors[1:], context):
                        yield result
                except IndexError:
                    iterated = context.eval_node(self._eval_node())
                    if self.array_type == 'dict':
                        yield iterated, context.eval_node(self._eval_node(2))
                    else:
                        yield iterated

    @memoize_default(default=[])
    @common.to_list
    def _iterate(self):
        comp_fors = tuple(self._get_comp_for().get_comp_fors())
        for result in self._nested(comp_fors):
            yield result

    def py__iter__(self):
        for set_ in self._iterate():
            yield context.LazyKnownContexts(set_)

    def __repr__(self):
        return "<%s of %s>" % (type(self).__name__, self._atom)


class ArrayMixin(object):
    def get_filters(self, search_global, until_position=None, origin_scope=None):
        # `array.type` is a string with the type, e.g. 'list'.
        compiled_obj = compiled.builtin_from_name(self.evaluator, self.array_type)
        yield SpecialMethodFilter(self, self.builtin_methods, compiled_obj)
        for typ in compiled_obj.execute_evaluated(self):
            for filter in typ.get_filters():
                yield filter

    def py__bool__(self):
        return None  # We don't know the length, because of appends.

    def py__class__(self):
        return compiled.builtin_from_name(self.evaluator, self.array_type)

    @safe_property
    def parent(self):
        return self.evaluator.BUILTINS

    def dict_values(self):
        return unite(self._defining_context.eval_node(v) for k, v in self._items())


class ListComprehension(ArrayMixin, Comprehension):
    array_type = 'list'

    def py__getitem__(self, index):
        if isinstance(index, slice):
            return set([self])

        all_types = list(self.py__iter__())
        return all_types[index].infer()


class SetComprehension(ArrayMixin, Comprehension):
    array_type = 'set'


@has_builtin_methods
class DictComprehension(ArrayMixin, Comprehension):
    array_type = 'dict'

    def _get_comp_for(self):
        return self._get_comprehension().children[3]

    def py__iter__(self):
        for keys, values in self._iterate():
            yield context.LazyKnownContexts(keys)

    def py__getitem__(self, index):
        for keys, values in self._iterate():
            for k in keys:
                if isinstance(k, compiled.CompiledObject):
                    if k.obj == index:
                        return values
        return self.dict_values()

    def dict_values(self):
        return unite(values for keys, values in self._iterate())

    @register_builtin_method('values')
    def _imitate_values(self):
        lazy_context = context.LazyKnownContexts(self.dict_values())
        return set([FakeSequence(self.evaluator, 'list', [lazy_context])])

    @register_builtin_method('items')
    def _imitate_items(self):
        items = set(
            FakeSequence(
                self.evaluator, 'tuple'
                (context.LazyKnownContexts(keys), context.LazyKnownContexts(values))
            ) for keys, values in self._iterate()
        )

        return create_evaluated_sequence_set(self.evaluator, items, sequence_type='list')


class GeneratorComprehension(GeneratorMixin, Comprehension):
    pass


class SequenceLiteralContext(ArrayMixin, AbstractSequence):
    mapping = {'(': 'tuple',
               '[': 'list',
               '{': 'set'}

    def __init__(self, evaluator, defining_context, atom):
        super(SequenceLiteralContext, self).__init__(evaluator)
        self.atom = atom
        self._defining_context = defining_context

        if self.atom.type in ('testlist_star_expr', 'testlist'):
            self.array_type = 'tuple'
        else:
            self.array_type = SequenceLiteralContext.mapping[atom.children[0]]
            """The builtin name of the array (list, set, tuple or dict)."""

    def py__getitem__(self, index):
        """Here the index is an int/str. Raises IndexError/KeyError."""
        if self.array_type == 'dict':
            for key, value in self._items():
                for k in self._defining_context.eval_node(key):
                    if isinstance(k, compiled.CompiledObject) \
                            and index == k.obj:
                        return self._defining_context.eval_node(value)
            raise KeyError('No key found in dictionary %s.' % self)

        # Can raise an IndexError
        if isinstance(index, slice):
            return set([self])
        else:
            return self._defining_context.eval_node(self._items()[index])

    def py__iter__(self):
        """
        While values returns the possible values for any array field, this
        function returns the value for a certain index.
        """
        if self.array_type == 'dict':
            # Get keys.
            types = set()
            for k, _ in self._items():
                types |= self._defining_context.eval_node(k)
            # We don't know which dict index comes first, therefore always
            # yield all the types.
            for _ in types:
                yield context.LazyKnownContexts(types)
        else:
            for node in self._items():
                yield context.LazyTreeContext(self._defining_context, node)

            for addition in check_array_additions(self._defining_context, self):
                yield addition

    def _values(self):
        """Returns a list of a list of node."""
        if self.array_type == 'dict':
            return unite(v for k, v in self._items())
        else:
            return self._items()

    def _items(self):
        c = self.atom.children

        if self.atom.type in ('testlist_star_expr', 'testlist'):
            return c[::2]

        array_node = c[1]
        if array_node in (']', '}', ')'):
            return []  # Direct closing bracket, doesn't contain items.

        if array_node.type == 'testlist_comp':
            return array_node.children[::2]
        elif array_node.type == 'dictorsetmaker':
            kv = []
            iterator = iter(array_node.children)
            for key in iterator:
                op = next(iterator, None)
                if op is None or op == ',':
                    kv.append(key)  # A set.
                else:
                    assert op == ':'  # A dict.
                    kv.append((key, next(iterator)))
                    next(iterator, None)  # Possible comma.
            return kv
        else:
            return [array_node]

    def exact_key_items(self):
        """
        Returns a generator of tuples like dict.items(), where the key is
        resolved (as a string) and the values are still lazy contexts.
        """
        for key_node, value in self._items():
            for key in self._defining_context.eval_node(key_node):
                if precedence.is_string(key):
                    yield key.obj, context.LazyTreeContext(self._defining_context, value)

    def __repr__(self):
        return "<%s of %s>" % (self.__class__.__name__, self.atom)


@has_builtin_methods
class DictLiteralContext(SequenceLiteralContext):
    array_type = 'dict'

    def __init__(self, evaluator, defining_context, atom):
        super(SequenceLiteralContext, self).__init__(evaluator)
        self._defining_context = defining_context
        self.atom = atom

    @register_builtin_method('values')
    def _imitate_values(self):
        lazy_context = context.LazyKnownContexts(self.dict_values())
        return set([FakeSequence(self.evaluator, 'list', [lazy_context])])

    @register_builtin_method('items')
    def _imitate_items(self):
        lazy_contexts = [
            context.LazyKnownContext(FakeSequence(
                self.evaluator, 'tuple',
                (context.LazyTreeContext(self._defining_context, key_node),
                 context.LazyTreeContext(self._defining_context, value_node))
            )) for key_node, value_node in self._items()
        ]

        return set([FakeSequence(self.evaluator, 'list', lazy_contexts)])


class _FakeArray(SequenceLiteralContext):
    def __init__(self, evaluator, container, type):
        super(SequenceLiteralContext, self).__init__(evaluator)
        self.array_type = type
        self.atom = container
        # TODO is this class really needed?


class ImplicitTuple(_FakeArray):
    def __init__(self, evaluator, testlist):
        super(ImplicitTuple, self).__init__(evaluator, testlist, 'tuple')
        raise NotImplementedError
        self._testlist = testlist

    def _items(self):
        return self._testlist.children[::2]


class FakeSequence(_FakeArray):
    def __init__(self, evaluator, array_type, lazy_context_list):
        """
        type should be one of "tuple", "list"
        """
        super(FakeSequence, self).__init__(evaluator, None, array_type)
        self._lazy_context_list = lazy_context_list

    def _items(self):
        raise DeprecationWarning
        return self._context_list

    def py__getitem__(self, index):
        return set(self._lazy_context_list[index].infer())

    def py__iter__(self):
        return self._lazy_context_list

    def __repr__(self):
        return "<%s of %s>" % (type(self).__name__, self._lazy_context_list)


class FakeDict(_FakeArray):
    def __init__(self, evaluator, dct):
        super(FakeDict, self).__init__(evaluator, dct, 'dict')
        self._dct = dct

    def py__iter__(self):
        for key in self._dct:
            yield context.LazyKnownContext(compiled.create(self.evaluator, key))

    def py__getitem__(self, index):
        return self._dct[index].infer()

    def dict_values(self):
        return unite(lazy_context.infer() for lazy_context in self._dct.values())

    def _items(self):
        raise DeprecationWarning
        for key, values in self._dct.items():
            # TODO this is not proper. The values could be multiple values?!
            yield key, values[0]

    def exact_key_items(self):
        return self._dct.items()


class MergedArray(_FakeArray):
    def __init__(self, evaluator, arrays):
        super(MergedArray, self).__init__(evaluator, arrays, arrays[-1].array_type)
        self._arrays = arrays

    def py__iter__(self):
        for array in self._arrays:
            for lazy_context in array.py__iter__():
                yield lazy_context

    def py__getitem__(self, index):
        return unite(lazy_context.infer() for lazy_context in self.py__iter__())

    def _items(self):
        for array in self._arrays:
            for a in array._items():
                yield a

    def __len__(self):
        return sum(len(a) for a in self._arrays)


def unpack_tuple_to_dict(evaluator, types, exprlist):
    """
    Unpacking tuple assignments in for statements and expr_stmts.
    """
    if exprlist.type == 'name':
        return {exprlist.value: types}
    elif exprlist.type == 'atom' and exprlist.children[0] in '([':
        return unpack_tuple_to_dict(evaluator, types, exprlist.children[1])
    elif exprlist.type in ('testlist', 'testlist_comp', 'exprlist',
                           'testlist_star_expr'):
        dct = {}
        parts = iter(exprlist.children[::2])
        n = 0
        for lazy_context in py__iter__(evaluator, types, exprlist):
            n += 1
            try:
                part = next(parts)
            except StopIteration:
                # TODO this context is probably not right.
                analysis.add(next(iter(types)), 'value-error-too-many-values', part,
                             message="ValueError: too many values to unpack (expected %s)" % n)
            else:
                dct.update(unpack_tuple_to_dict(evaluator, lazy_context.infer(), part))
        has_parts = next(parts, None)
        if types and has_parts is not None:
            # TODO this context is probably not right.
            analysis.add(next(iter(types)), 'value-error-too-few-values', has_parts,
                         message="ValueError: need more than %s values to unpack" % n)
        return dct
    elif exprlist.type == 'power' or exprlist.type == 'atom_expr':
        # Something like ``arr[x], var = ...``.
        # This is something that is not yet supported, would also be difficult
        # to write into a dict.
        return {}
    elif exprlist.type == 'star_expr':  # `a, *b, c = x` type unpackings
        # Currently we're not supporting them.
        return {}
    raise NotImplementedError


def py__iter__(evaluator, types, node=None):
    debug.dbg('py__iter__')
    type_iters = []
    for typ in types:
        try:
            iter_method = typ.py__iter__
        except AttributeError:
            if node is not None:
                # TODO this context is probably not right.
                analysis.add(typ, 'type-error-not-iterable', node,
                             message="TypeError: '%s' object is not iterable" % typ)
        else:
            type_iters.append(iter_method())

    for lazy_contexts in zip_longest(*type_iters):
        yield context.get_merged_lazy_context(
            [l for l in lazy_contexts if l is not None]
        )


def py__iter__types(evaluator, types, node=None):
    """
    Calls `py__iter__`, but ignores the ordering in the end and just returns
    all types that it contains.
    """
    return unite(lazy_context.infer() for lazy_context in py__iter__(evaluator, types, node))


def py__getitem__(evaluator, context, types, trailer):
    from jedi.evaluate.representation import ClassContext
    from jedi.evaluate.instance import TreeInstance
    result = set()

    trailer_op, node, trailer_cl = trailer.children
    assert trailer_op == "["
    assert trailer_cl == "]"

    # special case: PEP0484 typing module, see
    # https://github.com/davidhalter/jedi/issues/663
    for typ in list(types):
        if isinstance(typ, (ClassContext, TreeInstance)):
            typing_module_types = pep0484.py__getitem__(context, typ, node)
            if typing_module_types is not None:
                types.remove(typ)
                result |= typing_module_types

    if not types:
        # all consumed by special cases
        return result

    for index in create_index_types(evaluator, context, node):
        if isinstance(index, (compiled.CompiledObject, Slice)):
            index = index.obj

        if type(index) not in (float, int, str, unicode, slice):
            # If the index is not clearly defined, we have to get all the
            # possiblities.
            for typ in list(types):
                if isinstance(typ, AbstractSequence) and typ.array_type == 'dict':
                    types.remove(typ)
                    result |= typ.dict_values()
            return result | py__iter__types(evaluator, types)

        for typ in types:
            # The actual getitem call.
            try:
                getitem = typ.py__getitem__
            except AttributeError:
                # TODO this context is probably not right.
                analysis.add(context, 'type-error-not-subscriptable', trailer_op,
                             message="TypeError: '%s' object is not subscriptable" % typ)
            else:
                try:
                    result |= getitem(index)
                except IndexError:
                    result |= py__iter__types(evaluator, set([typ]))
                except KeyError:
                    # Must be a dict. Lists don't raise KeyErrors.
                    result |= typ.dict_values()
    return result


def check_array_additions(context, sequence):
    """ Just a mapper function for the internal _check_array_additions """
    if sequence.array_type not in ('list', 'set'):
        # TODO also check for dict updates
        return set()

    return _check_array_additions(context, sequence)


@memoize_default(default=set())
@debug.increase_indent
def _check_array_additions(context, sequence):
    """
    Checks if a `Array` has "add" (append, insert, extend) statements:

    >>> a = [""]
    >>> a.append(1)
    """
    from jedi.evaluate import param

    debug.dbg('Dynamic array search for %s' % sequence, color='MAGENTA')
    module_context = context.get_root_context()
    if not settings.dynamic_array_additions or isinstance(module_context, compiled.CompiledObject):
        debug.dbg('Dynamic array search aborted.', color='MAGENTA')
        return set()

    def find_additions(context, arglist, add_name):
        params = list(param.TreeArguments(context.evaluator, context, arglist).unpack())
        result = set()
        if add_name in ['insert']:
            params = params[1:]
        if add_name in ['append', 'add', 'insert']:
            for key, lazy_context in params:
                result.add(lazy_context)
        elif add_name in ['extend', 'update']:
            for key, lazy_context in params:
                result |= set(py__iter__(context.evaluator, lazy_context.infer()))
        return result

    temp_param_add, settings.dynamic_params_for_other_modules = \
        settings.dynamic_params_for_other_modules, False

    is_list = sequence.name.string_name == 'list'
    search_names = (['append', 'extend', 'insert'] if is_list else ['add', 'update'])

    added_types = set()
    for add_name in search_names:
        try:
            possible_names = module_context.tree_node.used_names[add_name]
        except KeyError:
            continue
        else:
            for name in possible_names:
                context_node = context.tree_node
                if not (context_node.start_pos < name.start_pos < context_node.end_pos):
                    continue
                trailer = name.parent
                power = trailer.parent
                trailer_pos = power.children.index(trailer)
                try:
                    execution_trailer = power.children[trailer_pos + 1]
                except IndexError:
                    continue
                else:
                    if execution_trailer.type != 'trailer' \
                            or execution_trailer.children[0] != '(' \
                            or execution_trailer.children[1] == ')':
                        continue

                random_context = context.create_context(name)

                with recursion.execution_allowed(context.evaluator, power) as allowed:
                    if allowed:
                        found = helpers.evaluate_call_of_leaf(
                            random_context,
                            name,
                            cut_own_trailer=True
                        )
                        if sequence in found:
                            # The arrays match. Now add the results
                            added_types |= find_additions(
                                random_context,
                                execution_trailer.children[1],
                                add_name
                            )

    # reset settings
    settings.dynamic_params_for_other_modules = temp_param_add
    debug.dbg('Dynamic array result %s' % added_types, color='MAGENTA')
    return added_types


def get_dynamic_array_instance(instance):
    """Used for set() and list() instances."""
    if not settings.dynamic_array_additions:
        return instance.var_args

    ai = _ArrayInstance(instance)
    from jedi.evaluate import param
    return param.ValuesArguments([[ai]])


class _ArrayInstance(object):
    """
    Used for the usage of set() and list().
    This is definitely a hack, but a good one :-)
    It makes it possible to use set/list conversions.

    In contrast to Array, ListComprehension and all other iterable types, this
    is something that is only used inside `evaluate/compiled/fake/builtins.py`
    and therefore doesn't need filters, `py__bool__` and so on, because
    we don't use these operations in `builtins.py`.
    """
    def __init__(self, instance):
        self.instance = instance
        self.var_args = instance.var_args

    def py__iter__(self):
        var_args = self.var_args
        try:
            _, lazy_context = next(var_args.unpack())
        except StopIteration:
            pass
        else:
            for lazy in py__iter__(self.instance.evaluator, lazy_context.infer()):
                yield lazy

        from jedi.evaluate import param
        if isinstance(var_args, param.TreeArguments):
            additions = _check_array_additions(var_args.context, self.instance)
            for addition in additions:
                yield addition


class Slice(context.Context):
    def __init__(self, context, start, stop, step):
        super(Slice, self).__init__(
            context.evaluator,
            parent_context=context.evaluator.BUILTINS
        )
        self._context = context
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

            result = self._context.eval_node(element)
            if len(result) != 1:
                # For simplicity, we want slices to be clear defined with just
                # one type.  Otherwise we will return an empty slice object.
                raise IndexError
            try:
                return list(result)[0].obj
            except AttributeError:
                return None

        try:
            return slice(get(self._start), get(self._stop), get(self._step))
        except IndexError:
            return slice(None, None, None)


def create_index_types(evaluator, context, index):
    """
    Handles slices in subscript nodes.
    """
    if index == ':':
        # Like array[:]
        return set([Slice(context, None, None, None)])
    elif index.type == 'subscript':  # subscript is a slice operation.
        # Like array[:3]
        result = []
        for el in index.children:
            if el == ':':
                if not result:
                    result.append(None)
            elif el.type == 'sliceop':
                if len(el.children) == 2:
                    result.append(el.children[1])
            else:
                result.append(el)
        result += [None] * (3 - len(result))

        return set([Slice(context, *result)])

    # No slices
    return context.eval_node(index)
