"""
We need to somehow work with the typing objects. Since the typing objects are
pretty bare we need to add all the Jedi customizations to make them work as
values.

This file deals with all the typing.py cases.
"""
from jedi import debug
from jedi.inference.cache import inference_state_method_cache
from jedi.inference.compiled import builtin_from_name
from jedi.inference.base_value import ValueSet, NO_VALUES, Value, \
    iterator_to_value_set, ValueWrapper, LazyValueWrapper
from jedi.inference.lazy_value import LazyKnownValues
from jedi.inference.value.iterable import SequenceLiteralValue
from jedi.inference.arguments import repack_with_argument_clinic
from jedi.inference.utils import to_list
from jedi.inference.filters import FilterWrapper
from jedi.inference.names import NameWrapper, AbstractTreeName, \
    AbstractNameDefinition, ValueName
from jedi.inference.helpers import is_string
from jedi.inference.value.klass import ClassMixin
from jedi.inference.context import ClassContext
from jedi.inference.gradual.base import BaseTypingValue
from jedi.inference.gradual.type_var import TypeVarClass, TypeVar

_PROXY_CLASS_TYPES = 'Tuple Generic Protocol Callable Type'.split()
_TYPE_ALIAS_TYPES = {
    'List': 'builtins.list',
    'Dict': 'builtins.dict',
    'Set': 'builtins.set',
    'FrozenSet': 'builtins.frozenset',
    'ChainMap': 'collections.ChainMap',
    'Counter': 'collections.Counter',
    'DefaultDict': 'collections.defaultdict',
    'Deque': 'collections.deque',
}
_PROXY_TYPES = 'Optional Union ClassVar'.split()


class TypingModuleName(NameWrapper):
    def infer(self):
        return ValueSet(self._remap())

    def _remap(self):
        name = self.string_name
        inference_state = self.parent_context.inference_state
        try:
            actual = _TYPE_ALIAS_TYPES[name]
        except KeyError:
            pass
        else:
            yield TypeAlias.create_cached(inference_state, self.parent_context, self.tree_name, actual)
            return

        if name in _PROXY_CLASS_TYPES:
            yield TypingClassValue.create_cached(inference_state, self.parent_context, self.tree_name)
        elif name in _PROXY_TYPES:
            yield TypingValue.create_cached(inference_state, self.parent_context, self.tree_name)
        elif name == 'runtime':
            # We don't want anything here, not sure what this function is
            # supposed to do, since it just appears in the stubs and shouldn't
            # have any effects there (because it's never executed).
            return
        elif name == 'TypeVar':
            yield TypeVarClass.create_cached(inference_state, self.parent_context, self.tree_name)
        elif name == 'Any':
            yield Any.create_cached(inference_state, self.parent_context, self.tree_name)
        elif name == 'TYPE_CHECKING':
            # This is needed for e.g. imports that are only available for type
            # checking or are in cycles. The user can then check this variable.
            yield builtin_from_name(inference_state, u'True')
        elif name == 'overload':
            yield OverloadFunction.create_cached(inference_state, self.parent_context, self.tree_name)
        elif name == 'NewType':
            yield NewTypeFunction.create_cached(inference_state, self.parent_context, self.tree_name)
        elif name == 'cast':
            yield CastFunction.create_cached(inference_state, self.parent_context, self.tree_name)
        elif name == 'TypedDict':
            # TODO doesn't even exist in typeshed/typing.py, yet. But will be
            # added soon.
            pass
        elif name in ('no_type_check', 'no_type_check_decorator'):
            # This is not necessary, as long as we are not doing type checking.
            for c in self._wrapped_name.infer():  # Fuck my life Python 2
                yield c
        else:
            # Everything else shouldn't be relevant for type checking.
            for c in self._wrapped_name.infer():  # Fuck my life Python 2
                yield c


class TypingModuleFilterWrapper(FilterWrapper):
    name_wrapper_class = TypingModuleName


class _WithIndexBase(BaseTypingValue):
    def __init__(self, inference_state, parent_context, name, index_value, value_of_index):
        super(_WithIndexBase, self).__init__(inference_state, parent_context, name)
        self._index_value = index_value
        self._context_of_index = value_of_index

    def __repr__(self):
        return '<%s: %s[%s]>' % (
            self.__class__.__name__,
            self._tree_name.value,
            self._index_value,
        )


class TypingValueWithIndex(_WithIndexBase):
    def execute_annotation(self):
        string_name = self._tree_name.value

        if string_name == 'Union':
            # This is kind of a special case, because we have Unions (in Jedi
            # ValueSets).
            return self.gather_annotation_classes().execute_annotation()
        elif string_name == 'Optional':
            # Optional is basically just saying it's either None or the actual
            # type.
            return self.gather_annotation_classes().execute_annotation() \
                | ValueSet([builtin_from_name(self.inference_state, u'None')])
        elif string_name == 'Type':
            # The type is actually already given in the index_value
            return ValueSet([self._index_value])
        elif string_name == 'ClassVar':
            # For now don't do anything here, ClassVars are always used.
            return self._index_value.execute_annotation()

        cls = globals()[string_name]
        return ValueSet([cls(
            self.inference_state,
            self.parent_context,
            self._tree_name,
            self._index_value,
            self._context_of_index
        )])

    def gather_annotation_classes(self):
        return ValueSet.from_sets(
            _iter_over_arguments(self._index_value, self._context_of_index)
        )


class TypingValue(BaseTypingValue):
    index_class = TypingValueWithIndex
    py__simple_getitem__ = None

    def py__getitem__(self, index_value_set, contextualized_node):
        return ValueSet(
            self.index_class.create_cached(
                self.inference_state,
                self.parent_context,
                self._tree_name,
                index_value,
                value_of_index=contextualized_node.context)
            for index_value in index_value_set
        )


class _TypingClassMixin(ClassMixin):
    def py__bases__(self):
        return [LazyKnownValues(
            self.inference_state.builtins_module.py__getattribute__('object')
        )]

    def get_metaclasses(self):
        return []

    @property
    def name(self):
        return ValueName(self, self._tree_name)


class TypingClassValueWithIndex(_TypingClassMixin, TypingValueWithIndex):

    @inference_state_method_cache()
    def get_generics(self):
        return list(_iter_over_arguments(self._index_value, self._context_of_index))


class TypingClassValue(_TypingClassMixin, TypingValue):
    index_class = TypingClassValueWithIndex


def _iter_over_arguments(maybe_tuple_value, defining_context):
    def iterate():
        if isinstance(maybe_tuple_value, SequenceLiteralValue):
            for lazy_value in maybe_tuple_value.py__iter__(contextualized_node=None):
                yield lazy_value.infer()
        else:
            yield ValueSet([maybe_tuple_value])

    def resolve_forward_references(value_set):
        for value in value_set:
            if is_string(value):
                from jedi.inference.gradual.annotation import _get_forward_reference_node
                node = _get_forward_reference_node(defining_context, value.get_safe_value())
                if node is not None:
                    for c in defining_context.infer_node(node):
                        yield c
            else:
                yield value

    for value_set in iterate():
        yield ValueSet(resolve_forward_references(value_set))


class TypeAlias(LazyValueWrapper):
    def __init__(self, parent_context, origin_tree_name, actual):
        self.inference_state = parent_context.inference_state
        self.parent_context = parent_context
        self._origin_tree_name = origin_tree_name
        self._actual = actual  # e.g. builtins.list

    @property
    def name(self):
        return ValueName(self, self._origin_tree_name)

    def py__name__(self):
        return self.name.string_name

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self._actual)

    def _get_wrapped_value(self):
        module_name, class_name = self._actual.split('.')
        if self.inference_state.environment.version_info.major == 2 and module_name == 'builtins':
            module_name = '__builtin__'

        # TODO use inference_state.import_module?
        from jedi.inference.imports import Importer
        module, = Importer(
            self.inference_state, [module_name], self.inference_state.builtins_module
        ).follow()
        classes = module.py__getattribute__(class_name)
        # There should only be one, because it's code that we control.
        assert len(classes) == 1, classes
        cls = next(iter(classes))
        return cls


class _GetItemMixin(object):
    def _get_getitem_values(self, index):
        args = _iter_over_arguments(self._index_value, self._context_of_index)
        for i, values in enumerate(args):
            if i == index:
                return values

        debug.warning('No param #%s found for annotation %s', index, self._index_value)
        return NO_VALUES


class Callable(_WithIndexBase, _GetItemMixin):
    def py__call__(self, arguments):
        # The 0th index are the arguments.
        return self._get_getitem_values(1).execute_annotation()


class Tuple(LazyValueWrapper, _GetItemMixin):
    def __init__(self, inference_state, parent_context, name, index_value, value_of_index):
        self.inference_state = inference_state
        self.parent_context = parent_context
        self._index_value = index_value
        self._context_of_index = value_of_index

    def _is_homogenous(self):
        # To specify a variable-length tuple of homogeneous type, Tuple[T, ...]
        # is used.
        if isinstance(self._index_value, SequenceLiteralValue):
            entries = self._index_value.get_tree_entries()
            if len(entries) == 2 and entries[1] == '...':
                return True
        return False

    def py__simple_getitem__(self, index):
        if self._is_homogenous():
            return self._get_getitem_values(0).execute_annotation()
        else:
            if isinstance(index, int):
                return self._get_getitem_values(index).execute_annotation()

            debug.dbg('The getitem type on Tuple was %s' % index)
            return NO_VALUES

    def py__iter__(self, contextualized_node=None):
        if self._is_homogenous():
            yield LazyKnownValues(self._get_getitem_values(0).execute_annotation())
        else:
            if isinstance(self._index_value, SequenceLiteralValue):
                for i in range(self._index_value.py__len__()):
                    yield LazyKnownValues(self._get_getitem_values(i).execute_annotation())

    def py__getitem__(self, index_value_set, contextualized_node):
        if self._is_homogenous():
            return self._get_getitem_values(0).execute_annotation()

        return ValueSet.from_sets(
            _iter_over_arguments(self._index_value, self._context_of_index)
        ).execute_annotation()

    def _get_wrapped_value(self):
        tuple_, = self.inference_state.builtins_module \
            .py__getattribute__('tuple').execute_annotation()
        return tuple_


class Generic(_WithIndexBase, _GetItemMixin):
    pass


class Protocol(_WithIndexBase, _GetItemMixin):
    pass


class Any(BaseTypingValue):
    def execute_annotation(self):
        debug.warning('Used Any - returned no results')
        return NO_VALUES


class OverloadFunction(BaseTypingValue):
    @repack_with_argument_clinic('func, /')
    def py__call__(self, func_value_set):
        # Just pass arguments through.
        return func_value_set


class NewTypeFunction(BaseTypingValue):
    def py__call__(self, arguments):
        ordered_args = arguments.unpack()
        next(ordered_args, (None, None))
        _, second_arg = next(ordered_args, (None, None))
        if second_arg is None:
            return NO_VALUES
        return ValueSet(
            NewType(
                self.inference_state,
                contextualized_node.context,
                contextualized_node.node,
                second_arg.infer(),
            ) for contextualized_node in arguments.get_calling_nodes())


class NewType(Value):
    def __init__(self, inference_state, parent_context, tree_node, type_value_set):
        super(NewType, self).__init__(inference_state, parent_context)
        self._type_value_set = type_value_set
        self.tree_node = tree_node

    def py__call__(self, arguments):
        return self._type_value_set.execute_annotation()


class CastFunction(BaseTypingValue):
    @repack_with_argument_clinic('type, object, /')
    def py__call__(self, type_value_set, object_value_set):
        return type_value_set.execute_annotation()


class BoundTypeVarName(AbstractNameDefinition):
    """
    This type var was bound to a certain type, e.g. int.
    """
    def __init__(self, type_var, value_set):
        self._type_var = type_var
        self.parent_context = type_var.parent_context
        self._value_set = value_set

    def infer(self):
        def iter_():
            for value in self._value_set:
                # Replace any with the constraints if they are there.
                if isinstance(value, Any):
                    for constraint in self._type_var.constraints:
                        yield constraint
                else:
                    yield value
        return ValueSet(iter_())

    def py__name__(self):
        return self._type_var.py__name__()

    def __repr__(self):
        return '<%s %s -> %s>' % (self.__class__.__name__, self.py__name__(), self._value_set)


class TypeVarFilter(object):
    """
    A filter for all given variables in a class.

        A = TypeVar('A')
        B = TypeVar('B')
        class Foo(Mapping[A, B]):
            ...

    In this example we would have two type vars given: A and B
    """
    def __init__(self, generics, type_vars):
        self._generics = generics
        self._type_vars = type_vars

    def get(self, name):
        for i, type_var in enumerate(self._type_vars):
            if type_var.py__name__() == name:
                try:
                    return [BoundTypeVarName(type_var, self._generics[i])]
                except IndexError:
                    return [type_var.name]
        return []

    def values(self):
        # The values are not relevant. If it's not searched exactly, the type
        # vars are just global and should be looked up as that.
        return []


class AnnotatedClassContext(ClassContext):
    def get_filters(self, *args, **kwargs):
        filters = super(AnnotatedClassContext, self).get_filters(
            *args, **kwargs
        )
        for f in filters:
            yield f

        # The type vars can only be looked up if it's a global search and
        # not a direct lookup on the class.
        yield self._value.get_type_var_filter()


class AbstractAnnotatedClass(ClassMixin, ValueWrapper):
    def get_type_var_filter(self):
        return TypeVarFilter(self.get_generics(), self.list_type_vars())

    def is_same_class(self, other):
        if not isinstance(other, AbstractAnnotatedClass):
            return False

        if self.tree_node != other.tree_node:
            # TODO not sure if this is nice.
            return False
        given_params1 = self.get_generics()
        given_params2 = other.get_generics()

        if len(given_params1) != len(given_params2):
            # If the amount of type vars doesn't match, the class doesn't
            # match.
            return False

        # Now compare generics
        return all(
            any(
                # TODO why is this ordering the correct one?
                cls2.is_same_class(cls1)
                for cls1 in class_set1
                for cls2 in class_set2
            ) for class_set1, class_set2 in zip(given_params1, given_params2)
        )

    def py__call__(self, arguments):
        instance, = super(AbstractAnnotatedClass, self).py__call__(arguments)
        return ValueSet([InstanceWrapper(instance)])

    def get_generics(self):
        raise NotImplementedError

    def define_generics(self, type_var_dict):
        changed = False
        new_generics = []
        for generic_set in self.get_generics():
            values = NO_VALUES
            for generic in generic_set:
                if isinstance(generic, (AbstractAnnotatedClass, TypeVar)):
                    result = generic.define_generics(type_var_dict)
                    values |= result
                    if result != ValueSet({generic}):
                        changed = True
                else:
                    values |= ValueSet([generic])
            new_generics.append(values)

        if not changed:
            # There might not be any type vars that change. In that case just
            # return itself, because it does not make sense to potentially lose
            # cached results.
            return ValueSet([self])

        return ValueSet([GenericClass(
            self._wrapped_value,
            generics=tuple(new_generics)
        )])

    def _as_context(self):
        return AnnotatedClassContext(self)

    def __repr__(self):
        return '<%s: %s%s>' % (
            self.__class__.__name__,
            self._wrapped_value,
            list(self.get_generics()),
        )

    @to_list
    def py__bases__(self):
        for base in self._wrapped_value.py__bases__():
            yield LazyAnnotatedBaseClass(self, base)


class LazyGenericClass(AbstractAnnotatedClass):
    def __init__(self, class_value, index_value, value_of_index):
        super(LazyGenericClass, self).__init__(class_value)
        self._index_value = index_value
        self._context_of_index = value_of_index

    @inference_state_method_cache()
    def get_generics(self):
        return list(_iter_over_arguments(self._index_value, self._context_of_index))


class GenericClass(AbstractAnnotatedClass):
    def __init__(self, class_value, generics):
        super(GenericClass, self).__init__(class_value)
        self._generics = generics

    def get_generics(self):
        return self._generics


class LazyAnnotatedBaseClass(object):
    def __init__(self, class_value, lazy_base_class):
        self._class_value = class_value
        self._lazy_base_class = lazy_base_class

    @iterator_to_value_set
    def infer(self):
        for base in self._lazy_base_class.infer():
            if isinstance(base, AbstractAnnotatedClass):
                # Here we have to recalculate the given types.
                yield GenericClass.create_cached(
                    base.inference_state,
                    base._wrapped_value,
                    tuple(self._remap_type_vars(base)),
                )
            else:
                yield base

    def _remap_type_vars(self, base):
        filter = self._class_value.get_type_var_filter()
        for type_var_set in base.get_generics():
            new = NO_VALUES
            for type_var in type_var_set:
                if isinstance(type_var, TypeVar):
                    names = filter.get(type_var.py__name__())
                    new |= ValueSet.from_sets(
                        name.infer() for name in names
                    )
                else:
                    # Mostly will be type vars, except if in some cases
                    # a concrete type will already be there. In that
                    # case just add it to the value set.
                    new |= ValueSet([type_var])
            yield new


class InstanceWrapper(ValueWrapper):
    def py__stop_iteration_returns(self):
        for cls in self._wrapped_value.class_value.py__mro__():
            if cls.py__name__() == 'Generator':
                generics = cls.get_generics()
                try:
                    return generics[2].execute_annotation()
                except IndexError:
                    pass
            elif cls.py__name__() == 'Iterator':
                return ValueSet([builtin_from_name(self.inference_state, u'None')])
        return self._wrapped_value.py__stop_iteration_returns()
