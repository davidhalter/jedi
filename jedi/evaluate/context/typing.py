"""
We need to somehow work with the typing objects. Since the typing objects are
pretty bare we need to add all the Jedi customizations to make them work as
contexts.
"""
from parso.python import tree

from jedi import debug
from jedi.evaluate.compiled import builtin_from_name
from jedi.evaluate.base_context import ContextSet, NO_CONTEXTS
from jedi.evaluate.context.iterable import SequenceLiteralContext

_PROXY_TYPES = 'Optional Union Callable Type ClassVar Tuple Generic Protocol'.split()
_TYPE_ALIAS_TYPES = 'List Dict DefaultDict Set FrozenSet Counter Deque ChainMap'.split()


class _TypingBase(object):
    def __init__(self, name, typing_context):
        self._name = name
        self._context = typing_context

    def __getattr__(self, name):
        return getattr(self._context, name)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._context)


class TypingModuleWrapper(_TypingBase):
    def py__getattribute__(self, name_or_str, *args, **kwargs):
        result = self._context.py__getattribute__(name_or_str)
        if kwargs.get('is_goto'):
            return result
        name = name_or_str.value if isinstance(name_or_str, tree.Name) else name_or_str
        return ContextSet.from_iterable(_remap(c, name) for c in result)


def _remap(context, name):
    if name in _PROXY_TYPES:
        return TypingProxy(name, context)
    elif name in _TYPE_ALIAS_TYPES:
        # TODO
        raise NotImplementedError
    elif name == 'TypeVar':
        raise NotImplementedError
        return TypeVar(context)
    elif name == 'Any':
        return Any(context)
    elif name == 'TYPE_CHECKING':
        # This is needed for e.g. imports that are only available for type
        # checking or are in cycles. The user can then check this variable.
        return builtin_from_name(context.evaluator, u'True')
    elif name == 'overload':
        # TODO implement overload
        return context
    elif name == 'cast':
        # TODO implement cast
        return context
    elif name == 'TypedDict':
        # TODO implement
        # e.g. Movie = TypedDict('Movie', {'name': str, 'year': int})
        return context
    elif name in ('no_type_check', 'no_type_check_decorator'):
        # This is not necessary, as long as we are not doing type checking.
        return context
    return context


class TypingProxy(_TypingBase):
    py__simple_getitem__ = None

    def py__getitem__(self, index_context, contextualized_node):
        return ContextSet(TypingProxyWithIndex(self._name, self._context, index_context))


class _WithIndexBase(_TypingBase):
    def __init__(self, name, class_context, index_context):
        super(_WithIndexBase, self).__init__(name, class_context)
        self._index_context = index_context

    def __repr__(self):
        return '%s(%s, %s)' % (
            self.__class__.__name__,
            self._context,
            self._index_context
        )

    def _execute_annotations_for_all_indexes(self):
        return ContextSet.from_sets(
            _iter_over_arguments(self._index_context)
        ).execute_annotation()


class TypingProxyWithIndex(_WithIndexBase):
    def execute_annotation(self):
        name = self._name
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
    # TODO implement typevars
    pass


# For pure type inference these two classes are basically the same. It's much
# more interesting once you do type checking.
Protocol = Generic


class Any(_TypingBase):
    def __init__(self):
        # Any is basically object, when it comes to type inference/completions.
        # This is obviously not correct, but let's just use this for now.
        context = ContextSet(builtin_from_name(self.evaluator, u'object'))
        super(_WithIndexBase, self).__init__(context)
