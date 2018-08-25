"""
We need to somehow work with the typing objects. Since the typing objects are
pretty bare we need to add all the Jedi customizations to make them work as
contexts.
"""
from jedi import debug
from jedi.evaluate.compiled import builtin_from_name, CompiledObject
from jedi.evaluate.base_context import ContextSet, NO_CONTEXTS, Context
from jedi.evaluate.context.iterable import SequenceLiteralContext
from jedi.evaluate.filters import FilterWrapper, NameWrapper, \
    AbstractTreeName

_PROXY_CLASS_TYPES = 'Tuple Generic Protocol'.split()
_TYPE_ALIAS_TYPES = 'List Dict DefaultDict Set FrozenSet Counter Deque ChainMap'.split()
_PROXY_TYPES = 'Optional Union Callable Type ClassVar'.split()


class TypingName(AbstractTreeName):
    def __init__(self, context, other_name):
        super(TypingName, self).__init__(context.parent_context, other_name.tree_name)
        self._context = context

    def infer(self):
        return ContextSet(self._context)


class _BaseTypingContext(Context):
    def __init__(self, name):
        super(_BaseTypingContext, self).__init__(
            name.parent_context.evaluator,
            parent_context=name.parent_context,
        )
        self._name = name

    @property
    def name(self):
        return TypingName(self, self._name)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._name.string_name)


class TypingModuleName(NameWrapper):
    def infer(self):
        return ContextSet.from_iterable(self._remap())

    def _remap(self):
        # TODO we don't want the SpecialForm bullshit
        name = self.string_name
        evaluator = self.parent_context.evaluator
        if name in (_PROXY_CLASS_TYPES + _TYPE_ALIAS_TYPES):
            yield TypingClassContext(self)
        elif name == _PROXY_TYPES:
            yield TypingContext(self)
        elif name == 'runtime':
            # We don't want anything here, not sure what this function is
            # supposed to do, since it just appears in the stubs and shouldn't
            # have any effects there (because it's never executed).
            return
        elif name == 'TypeVar':
            yield TypeVarClass(evaluator)
        elif name == 'Any':
            yield Any()
        elif name == 'TYPE_CHECKING':
            # This is needed for e.g. imports that are only available for type
            # checking or are in cycles. The user can then check this variable.
            yield builtin_from_name(evaluator, u'True')
        elif name == 'overload':
            # TODO implement overload
            pass
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
    def __init__(self, name, index_context):
        super(_WithIndexBase, self).__init__(name)
        self._index_context = index_context

    def __repr__(self):
        return '<%s: %s[%s]>' % (
            self.__class__.__name__,
            self._name.string_name,
            self._index_context,
        )

    def _execute_annotations_for_all_indexes(self):
        return ContextSet.from_sets(
            _iter_over_arguments(self._index_context)
        ).execute_annotation()


class TypingContextWithIndex(_WithIndexBase):
    def execute_annotation(self):
        name = self._name
        if name in _TYPE_ALIAS_TYPES:
            debug.warning('type aliases are not yet implemented')
            return NO_CONTEXTS

        if name == 'Union':
            # This is kind of a special case, because we have Unions (in Jedi
            # ContextSets).
            return self._execute_annotations_for_all_indexes()
        elif name == 'Optional':
            # Optional is basically just saying it's either None or the actual
            # type.
            return ContextSet(self._context) \
                | ContextSet(builtin_from_name(self.evaluator, u'None'))
        elif name == 'Type':
            # The type is actually already given in the index_context
            return ContextSet(self._index_context)
        elif name == 'ClassVar':
            # For now don't do anything here, ClassVars are always used.
            return self._context.execute_annotation()

        cls = globals()[name]
        return ContextSet(cls(name, self._context, self._index_context))


class TypingContext(_BaseTypingContext):
    index_class = TypingContextWithIndex
    py__simple_getitem__ = None

    def py__getitem__(self, index_context_set, contextualized_node):
        return ContextSet.from_iterable(
            self.index_class(self._name, index_context)
            for index_context in index_context_set
        )


class TypingClassMixin(object):
    def py__mro__(self):
        return (self,)


class TypingClassContextWithIndex(TypingClassMixin, TypingContextWithIndex):
    pass


class TypingClassContext(TypingClassMixin, TypingContext):
    index_class = TypingClassContextWithIndex


def _iter_over_arguments(maybe_tuple_context):
    if isinstance(maybe_tuple_context, SequenceLiteralContext):
        for lazy_context in maybe_tuple_context.py__iter__():
            yield lazy_context.infer()
    else:
        yield ContextSet(maybe_tuple_context)


class _ContainerBase(_WithIndexBase):
    def get_filters(self):
        pass

    def _get_getitem_contexts(self, index):
        for i, contexts in enumerate(_iter_over_arguments(self._index_context)):
            if i == index:
                return contexts

        debug.warning('No param #%s found for annotation %s', index, self._index_context)
        return NO_CONTEXTS


class Callable(_ContainerBase):
    def py__call__(self, arguments):
        # The 0th index are the arguments.
        return self._get_getitem_contexts(1)


class Tuple(_ContainerBase):
    def _is_homogenous(self):
        # To specify a variable-length tuple of homogeneous type, Tuple[T, ...]
        # is used.
        if isinstance(self._index_context, SequenceLiteralContext):
            pass
        return False

    def py__simple_getitem__(self, index):
        if self._is_homogenous():
            return self._get_getitem_contexts(0)
        else:
            if isinstance(index, int):
                return self._get_getitem_contexts(index).execute_annotation()

            debug.dbg('The getitem type on Tuple was %s' % index)
            return NO_CONTEXTS

    def py__getitem__(self):
        if self._is_homogenous():
            return self._get_getitem_contexts(0).execute_annotation()

        return self._execute_annotations_for_all_indexes()


class Generic(_ContainerBase):
    pass


class Protocol(_ContainerBase):
    pass


class Any(_BaseTypingContext):
    def __init__(self):
        # Any is basically object, when it comes to type inference/completions.
        # This is obviously not correct, but let's just use this for now.
        context = ContextSet(builtin_from_name(self.evaluator, u'object'))
        super(Any, self).__init__(context)

    def execute_annotation(self):
        debug.warning('Used Any, which is not implemented, yet.')
        return NO_CONTEXTS


class GenericClass(object):
    def __init__(self, class_context, ):
        self._class_context = class_context

    def __getattr__(self, name):
        return getattr(self._class_context, name)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._class_context)


class TypeVarClass(Context):
    def py__call__(self, arguments):
        unpacked = arguments.unpack()

        key, lazy_context = next(unpacked, (None, None))
        name = self._find_name(lazy_context)
        # The name must be given, otherwise it's useless.
        if name is None or key is not None:
            debug.warning('Found a variable without a name %s', arguments)
            return NO_CONTEXTS

        return ContextSet(TypeVar(self.evaluator, name, unpacked))

    def _find_name(self, lazy_context):
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


class TypeVar(Context):
    def __init__(self, evaluator, name, unpacked_args):
        super(TypeVar, self).__init__(evaluator)
        self._name = name

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

    def execute_annotation(self):
        if self._bound_lazy_context is not None:
            return self._bound_lazy_context.infer()
        return NO_CONTEXTS

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self._name)
