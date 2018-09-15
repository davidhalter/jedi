"""
We need to somehow work with the typing objects. Since the typing objects are
pretty bare we need to add all the Jedi customizations to make them work as
contexts.
"""
from jedi import debug
from jedi.evaluate.cache import evaluator_method_cache
from jedi.evaluate.compiled import builtin_from_name, CompiledObject
from jedi.evaluate.base_context import ContextSet, NO_CONTEXTS, Context, iterator_to_context_set
from jedi.evaluate.lazy_context import LazyKnownContexts, LazyKnownContext
from jedi.evaluate.context.iterable import SequenceLiteralContext
from jedi.evaluate.arguments import repack_with_argument_clinic, unpack_arglist
from jedi.evaluate.utils import to_list
from jedi.evaluate.filters import FilterWrapper, NameWrapper, \
    AbstractTreeName, AbstractNameDefinition, ContextName
from jedi.evaluate.helpers import is_string
from jedi.evaluate.imports import Importer
from jedi.evaluate.context import ClassContext

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


class TypingName(AbstractTreeName):
    def __init__(self, context, other_name):
        super(TypingName, self).__init__(context.parent_context, other_name.tree_name)
        self._context = context

    def infer(self):
        return ContextSet(self._context)


class _BaseTypingContext(Context):
    def __init__(self, evaluator, parent_context, tree_name):
        super(_BaseTypingContext, self).__init__(evaluator, parent_context)
        self._tree_name = tree_name

    @property
    def tree_node(self):
        return self._tree_name

    def get_filters(self, *args, **kwargs):
        # TODO this is obviously wrong.
        class EmptyFilter():
            def get(self, name):
                return []

            def values(self):
                return []

        yield EmptyFilter()

    @property
    def name(self):
        return ContextName(self, self.tree_name)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._tree_name.value)


class TypingModuleName(NameWrapper):
    def infer(self):
        return ContextSet.from_iterable(self._remap())

    def _remap(self):
        name = self.string_name
        evaluator = self.parent_context.evaluator
        try:
            actual = _TYPE_ALIAS_TYPES[name]
        except KeyError:
            pass
        else:
            yield TypeAlias.create_cached(evaluator, self.parent_context, self.tree_name, actual)
            return

        if name in _PROXY_CLASS_TYPES:
            yield TypingClassContext(evaluator, self.parent_context, self.tree_name)
        elif name in _PROXY_TYPES:
            yield TypingContext.create_cached(evaluator, self.parent_context, self.tree_name)
        elif name == 'runtime':
            # We don't want anything here, not sure what this function is
            # supposed to do, since it just appears in the stubs and shouldn't
            # have any effects there (because it's never executed).
            return
        elif name == 'TypeVar':
            yield TypeVarClass.create_cached(evaluator, self.parent_context, self.tree_name)
        elif name == 'Any':
            yield Any.create_cached(evaluator, self.parent_context, self.tree_name)
        elif name == 'TYPE_CHECKING':
            # This is needed for e.g. imports that are only available for type
            # checking or are in cycles. The user can then check this variable.
            yield builtin_from_name(evaluator, u'True')
        elif name == 'overload':
            yield OverloadFunction.create_cached(evaluator, self.parent_context, self.tree_name)
        elif name == 'cast':
            # TODO implement cast
            for c in self._wrapped_name.infer():  # Fuck my life Python 2
                yield c
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


class _WithIndexBase(_BaseTypingContext):
    def __init__(self, evaluator, parent_context, name, index_context, context_of_index):
        super(_WithIndexBase, self).__init__(evaluator, parent_context, name)
        self._index_context = index_context
        self._context_of_index = context_of_index

    def __repr__(self):
        return '<%s: %s[%s]>' % (
            self.__class__.__name__,
            self._tree_name.value,
            self._index_context,
        )

    def _execute_annotations_for_all_indexes(self):
        return ContextSet.from_sets(
            _iter_over_arguments(self._index_context, self._context_of_index)
        ).execute_annotation()


class TypingContextWithIndex(_WithIndexBase):
    def execute_annotation(self):
        string_name = self._tree_name.value

        if string_name == 'Union':
            # This is kind of a special case, because we have Unions (in Jedi
            # ContextSets).
            return self._execute_annotations_for_all_indexes()
        elif string_name == 'Optional':
            # Optional is basically just saying it's either None or the actual
            # type.
            return self._execute_annotations_for_all_indexes() \
                | ContextSet(builtin_from_name(self.evaluator, u'None'))
        elif string_name == 'Type':
            # The type is actually already given in the index_context
            return ContextSet(self._index_context)
        elif string_name == 'ClassVar':
            # For now don't do anything here, ClassVars are always used.
            return self._index_context.execute_annotation()

        cls = globals()[string_name]
        return ContextSet(cls(
            self.evaluator,
            self.parent_context,
            self._tree_name,
            self._index_context,
            self._context_of_index
        ))


class TypingContext(_BaseTypingContext):
    index_class = TypingContextWithIndex
    py__simple_getitem__ = None

    def py__getitem__(self, index_context_set, contextualized_node):
        return ContextSet.from_iterable(
            self.index_class.create_cached(
                self.evaluator,
                self.parent_context,
                self._tree_name,
                index_context,
                context_of_index=contextualized_node.context)
            for index_context in index_context_set
        )


class TypingClassMixin(object):
    def py__bases__(self,):
        return [LazyKnownContext(builtin_from_name(self.evaluator, u'object'))]


class TypingClassContextWithIndex(TypingClassMixin, TypingContextWithIndex):
    pass


class TypingClassContext(TypingClassMixin, TypingContext):
    index_class = TypingClassContextWithIndex


def _iter_over_arguments(maybe_tuple_context, defining_context):
    def iterate():
        if isinstance(maybe_tuple_context, SequenceLiteralContext):
            for lazy_context in maybe_tuple_context.py__iter__():
                yield lazy_context.infer()
        else:
            yield ContextSet(maybe_tuple_context)

    def resolve_forward_references(context_set):
        for context in context_set:
            if is_string(context):
                from jedi.evaluate.pep0484 import _get_forward_reference_node
                node = _get_forward_reference_node(defining_context, context.get_safe_value())
                if node is not None:
                    for c in defining_context.eval_node(node):
                        yield c
            else:
                yield context

    for context_set in iterate():
        yield ContextSet.from_iterable(resolve_forward_references(context_set))


class TypeAlias(object):
    def __init__(self, evaluator, parent_context, origin_tree_name, actual):
        self.evaluator = evaluator
        self.parent_context = parent_context
        self._origin_tree_name = origin_tree_name
        self._actual = actual  # e.g. builtins.list

    @property
    def name(self):
        return ContextName(self, self._origin_tree_name)

    def py__name__(self):
        return self.name.string_name

    def __getattr__(self, name):
        return getattr(self._get_type_alias_class(), name)

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self._actual)

    @evaluator_method_cache()
    def _get_type_alias_class(self):
        module_name, class_name = self._actual.split('.')
        if self.evaluator.environment.version_info.major == 2 and module_name == 'builtins':
            module_name = '__builtin__'

        module, = Importer(
            self.evaluator, [module_name], self.evaluator.builtins_module
        ).follow()
        classes = module.py__getattribute__(class_name)
        # There should only be one, because it's code that we control.
        assert len(classes) == 1, classes
        cls = next(iter(classes))
        return cls


class _ContainerBase(_WithIndexBase):
    def _get_getitem_contexts(self, index):
        args = _iter_over_arguments(self._index_context, self._context_of_index)
        for i, contexts in enumerate(args):
            if i == index:
                return contexts

        debug.warning('No param #%s found for annotation %s', index, self._index_context)
        return NO_CONTEXTS


class Callable(_ContainerBase):
    def py__call__(self, arguments):
        # The 0th index are the arguments.
        return self._get_getitem_contexts(1).execute_annotation()


class Tuple(_ContainerBase):
    def _is_homogenous(self):
        # To specify a variable-length tuple of homogeneous type, Tuple[T, ...]
        # is used.
        if isinstance(self._index_context, SequenceLiteralContext):
            entries = self._index_context.get_tree_entries()
            if len(entries) == 2 and entries[1] == '...':
                return True
        return False

    def py__simple_getitem__(self, index):
        if self._is_homogenous():
            return self._get_getitem_contexts(0).execute_annotation()
        else:
            if isinstance(index, int):
                return self._get_getitem_contexts(index).execute_annotation()

            debug.dbg('The getitem type on Tuple was %s' % index)
            return NO_CONTEXTS

    def py__iter__(self):
        if self._is_homogenous():
            while True:
                yield LazyKnownContexts(self._get_getitem_contexts(0).execute_annotation())
        else:
            if isinstance(self._index_context, SequenceLiteralContext):
                for i in range(self._index_context.py__len__()):
                    yield LazyKnownContexts(self._get_getitem_contexts(i).execute_annotation())

    def py__getitem__(self):
        if self._is_homogenous():
            return self._get_getitem_contexts(0).execute_annotation()

        return self._execute_annotations_for_all_indexes()


class Generic(_ContainerBase):
    pass


class Protocol(_ContainerBase):
    pass


class Any(_BaseTypingContext):
    def execute_annotation(self):
        debug.warning('Used Any - returned no results')
        return NO_CONTEXTS


class TypeVarClass(_BaseTypingContext):
    def py__call__(self, arguments):
        unpacked = arguments.unpack()

        key, lazy_context = next(unpacked, (None, None))
        var_name = self._find_string_name(lazy_context)
        # The name must be given, otherwise it's useless.
        if var_name is None or key is not None:
            debug.warning('Found a variable without a name %s', arguments)
            return NO_CONTEXTS

        return ContextSet(TypeVar.create_cached(
            self.evaluator,
            self.parent_context,
            self._tree_name,
            var_name,
            unpacked
        ))

    def _find_string_name(self, lazy_context):
        if lazy_context is None:
            return None

        context_set = lazy_context.infer()
        if not context_set:
            return None
        if len(context_set) > 1:
            debug.warning('Found multiple contexts for a type variable: %s', context_set)

        name_context = next(iter(context_set))
        if isinstance(name_context, CompiledObject):
            return name_context.get_safe_value(default=None)
        return None


class TypeVar(_BaseTypingContext):
    def __init__(self, evaluator, parent_context, tree_name, var_name, unpacked_args):
        super(TypeVar, self).__init__(evaluator, parent_context, tree_name)
        self._var_name = var_name

        self._constraints_lazy_contexts = []
        self._bound_lazy_context = None
        self._covariant_lazy_context = None
        self._contravariant_lazy_context = None
        for key, lazy_context in unpacked_args:
            if key is None:
                self._constraints_lazy_contexts.append(lazy_context)
            else:
                if key == 'bound':
                    self._bound_lazy_context = lazy_context
                elif key == 'covariant':
                    self._covariant_lazy_context = lazy_context
                elif key == 'contravariant':
                    self._contra_variant_lazy_context = lazy_context
                else:
                    debug.warning('Invalid TypeVar param name %s', key)

    def py__name__(self):
        return self._var_name

    def get_filters(self, *args, **kwargs):
        return iter([])

    def _get_classes(self):
        if self._bound_lazy_context is not None:
            return self._bound_lazy_context.infer()
        if self._constraints_lazy_contexts:
            return ContextSet.from_sets(
                l.infer() for l in self._constraints_lazy_contexts
            )
        debug.warning('Tried to infer a TypeVar without a given type')
        return NO_CONTEXTS

    @property
    def constraints(self):
        return ContextSet.from_sets(
            lazy.infer() for lazy in self._constraints_lazy_contexts
        )

    def execute_annotation(self):
        return self._get_classes().execute_annotation()

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.py__name__())


class OverloadFunction(_BaseTypingContext):
    @repack_with_argument_clinic('func, /')
    def py__call__(self, func_context_set):
        # Just pass arguments through.
        return func_context_set


class BoundTypeVarName(AbstractNameDefinition):
    """
    This type var was bound to a certain type, e.g. int.
    """
    def __init__(self, type_var, context_set):
        self._type_var = type_var
        self.parent_context = type_var.parent_context
        self._context_set = context_set

    def infer(self):
        def iter_():
            for context in self._context_set:
                # Replace any with the constraints if they are there.
                if isinstance(context, Any):
                    for constraint in self._type_var.constraints:
                        yield constraint
                else:
                    yield context
        return ContextSet.from_iterable(iter_())

    def py__name__(self):
        return self._type_var.py__name__()

    def __repr__(self):
        return '<%s %s -> %s>' % (self.__class__.__name__, self.py__name__(), self._context_set)


class TypeVarFilter(object):
    """
    A filter for all given variables in a class.

        A = TypeVar('A')
        B = TypeVar('B')
        class Foo(Mapping[A, B]):
            ...

    In this example we would have two type vars given: A and B
    """
    def __init__(self, given_types, type_vars):
        self._given_types = given_types
        self._type_vars = type_vars

    def get(self, name):
        for i, type_var in enumerate(self._type_vars):
            if type_var.py__name__() == name:
                try:
                    return [BoundTypeVarName(type_var, self._given_types[i])]
                except IndexError:
                    return [type_var.name]
        return []

    def values(self):
        # The values are not relevant. If it's not searched exactly, the type
        # vars are just global and should be looked up as that.
        return []


class _AbstractAnnotatedClass(ClassContext):
    def get_type_var_filter(self):
        return TypeVarFilter(self.get_given_types(), self.find_annotation_variables())

    def get_filters(self, search_global=False, *args, **kwargs):
        for f in super(_AbstractAnnotatedClass, self).get_filters(search_global, *args, **kwargs):
            yield f

        if search_global:
            # The type vars can only be looked up if it's a global search and
            # not a direct lookup on the class.
            yield self.get_type_var_filter()

    @evaluator_method_cache()
    def find_annotation_variables(self):
        found = []
        arglist = self.tree_node.get_super_arglist()
        if arglist is None:
            return []

        for stars, node in unpack_arglist(arglist):
            if stars:
                continue  # These are not relevant for this search.

            if node.type == 'atom_expr':
                trailer = node.children[-1]
                if trailer.type == 'trailer' and trailer.children[0] == '[':
                    for subscript_node in self._unpack_subscriptlist(trailer.children[1]):
                        type_var_set = self.parent_context.eval_node(subscript_node)
                        for type_var in type_var_set:
                            if isinstance(type_var, TypeVar) and type_var not in found:
                                found.append(type_var)
        return found

    def _unpack_subscriptlist(self, subscriptlist):
        if subscriptlist.type == 'subscriptlist':
            for subscript in subscriptlist.children[::2]:
                if subscript.type != 'subscript':
                    yield subscript
        else:
            if subscriptlist.type != 'subscript':
                yield subscriptlist

    def is_same_class(self, other):
        if not isinstance(other, _AbstractAnnotatedClass):
            return False

        if self.tree_node != other.tree_node:
            # TODO not sure if this is nice.
            return False

        given_params1 = self.get_given_types()
        given_params2 = other.get_given_types()
        if len(given_params1) != len(given_params2):
            # If the amount of type vars doesn't match, the class doesn't
            # match.
            return False

        # Now compare generics
        return all(
            any(
                cls1.is_same_class(cls2)
                for cls1 in class_set1
                for cls2 in class_set2
            ) for class_set1, class_set2 in zip(given_params1, given_params2)
        )

    def get_given_types(self):
        raise NotImplementedError

    def __repr__(self):
        return '<%s: %s%s>' % (
            self.__class__.__name__,
            self.name.string_name,
            self.get_given_types(),
        )

    @to_list
    def py__bases__(self):
        for base in super(_AbstractAnnotatedClass, self).py__bases__():
            yield LazyAnnotatedBaseClass(self, base)


class AnnotatedClass(_AbstractAnnotatedClass):
    def __init__(self, evaluator, parent_context, tree_node, index_context, context_of_index):
        super(AnnotatedClass, self).__init__(evaluator, parent_context, tree_node)
        self._index_context = index_context
        self._context_of_index = context_of_index

    @evaluator_method_cache()
    def get_given_types(self):
        return list(_iter_over_arguments(self._index_context, self._context_of_index))


class AnnotatedSubClass(_AbstractAnnotatedClass):
    def __init__(self, evaluator, parent_context, tree_node, given_types):
        super(AnnotatedSubClass, self).__init__(evaluator, parent_context, tree_node)
        self._given_types = given_types

    def get_given_types(self):
        return self._given_types


class LazyAnnotatedBaseClass(object):
    def __init__(self, class_context, lazy_base_class):
        self._class_context = class_context
        self._lazy_base_class = lazy_base_class

    @iterator_to_context_set
    def infer(self):
        for base in self._lazy_base_class.infer():
            if isinstance(base, _AbstractAnnotatedClass):
                # Here we have to recalculate the given types.
                yield AnnotatedSubClass.create_cached(
                    base.evaluator,
                    base.parent_context,
                    base.tree_node,
                    tuple(self._remap_type_vars(base)),
                )
            else:
                yield base

    def _remap_type_vars(self, base):
        filter = self._class_context.get_type_var_filter()
        for type_var_set in base.get_given_types():
            new = ContextSet()
            for type_var in type_var_set:
                if isinstance(type_var, TypeVar):
                    names = filter.get(type_var.py__name__())
                    new |= ContextSet.from_sets(
                        name.infer() for name in names
                    )
                else:
                    # Mostly will be type vars, except if in some cases
                    # a concrete type will already be there. In that
                    # case just add it to the context set.
                    new |= ContextSet(type_var)
            yield new
