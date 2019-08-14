"""
Contexts are the "values" that Python would return. However Contexts are at the
same time also the "values" that a user is currently sitting in.

A ContextSet is typically used to specify the return of a function or any other
static analysis operation. In jedi there are always multiple returns and not
just one.
"""
from functools import reduce
from operator import add
from parso.python.tree import ExprStmt, SyncCompFor

from jedi import debug
from jedi._compatibility import zip_longest, unicode
from jedi.parser_utils import clean_scope_docstring
from jedi.common import BaseContextSet, BaseContext
from jedi.inference.helpers import SimpleGetItemNotFound
from jedi.inference.utils import safe_property
from jedi.inference.cache import infer_state_as_method_param_cache
from jedi.cache import memoize_method

_sentinel = object()


class HelperContextMixin(object):
    def get_root_value(self):
        value = self
        while True:
            if value.parent_value is None:
                return value
            value = value.parent_value

    @classmethod
    @infer_state_as_method_param_cache()
    def create_cached(cls, *args, **kwargs):
        return cls(*args, **kwargs)

    def execute(self, arguments):
        return self.infer_state.execute(self, arguments=arguments)

    def execute_with_values(self, *value_list):
        from jedi.inference.arguments import ValuesArguments
        arguments = ValuesArguments([ContextSet([value]) for value in value_list])
        return self.infer_state.execute(self, arguments)

    def execute_annotation(self):
        return self.execute_with_values()

    def gather_annotation_classes(self):
        return ContextSet([self])

    def merge_types_of_iterate(self, valueualized_node=None, is_async=False):
        return ContextSet.from_sets(
            lazy_value.infer()
            for lazy_value in self.iterate(valueualized_node, is_async)
        )

    def py__getattribute__(self, name_or_str, name_value=None, position=None,
                           search_global=False, is_goto=False,
                           analysis_errors=True):
        """
        :param position: Position of the last statement -> tuple of line, column
        """
        if name_value is None:
            name_value = self
        from jedi.inference import finder
        f = finder.NameFinder(self.infer_state, self, name_value, name_or_str,
                              position, analysis_errors=analysis_errors)
        filters = f.get_filters(search_global)
        if is_goto:
            return f.filter_name(filters)
        return f.find(filters, attribute_lookup=not search_global)

    def py__await__(self):
        await_value_set = self.py__getattribute__(u"__await__")
        if not await_value_set:
            debug.warning('Tried to run __await__ on value %s', self)
        return await_value_set.execute_with_values()

    def infer_node(self, node):
        return self.infer_state.infer_element(self, node)

    def create_value(self, node, node_is_value=False, node_is_object=False):
        return self.infer_state.create_value(self, node, node_is_value, node_is_object)

    def iterate(self, valueualized_node=None, is_async=False):
        debug.dbg('iterate %s', self)
        if is_async:
            from jedi.inference.lazy_value import LazyKnownContexts
            # TODO if no __aiter__ values are there, error should be:
            # TypeError: 'async for' requires an object with __aiter__ method, got int
            return iter([
                LazyKnownContexts(
                    self.py__getattribute__('__aiter__').execute_with_values()
                        .py__getattribute__('__anext__').execute_with_values()
                        .py__getattribute__('__await__').execute_with_values()
                        .py__stop_iteration_returns()
                )  # noqa
            ])
        return self.py__iter__(valueualized_node)

    def is_sub_class_of(self, class_value):
        for cls in self.py__mro__():
            if cls.is_same_class(class_value):
                return True
        return False

    def is_same_class(self, class2):
        # Class matching should prefer comparisons that are not this function.
        if type(class2).is_same_class != HelperContextMixin.is_same_class:
            return class2.is_same_class(self)
        return self == class2


class Context(HelperContextMixin, BaseContext):
    """
    Should be defined, otherwise the API returns empty types.
    """
    predefined_names = {}
    """
    To be defined by subclasses.
    """
    tree_node = None

    @property
    def api_type(self):
        # By default just lower name of the class. Can and should be
        # overwritten.
        return self.__class__.__name__.lower()

    def py__getitem__(self, index_value_set, valueualized_node):
        from jedi.inference import analysis
        # TODO this value is probably not right.
        analysis.add(
            valueualized_node.value,
            'type-error-not-subscriptable',
            valueualized_node.node,
            message="TypeError: '%s' object is not subscriptable" % self
        )
        return NO_VALUES

    def py__iter__(self, valueualized_node=None):
        if valueualized_node is not None:
            from jedi.inference import analysis
            analysis.add(
                valueualized_node.value,
                'type-error-not-iterable',
                valueualized_node.node,
                message="TypeError: '%s' object is not iterable" % self)
        return iter([])

    def get_signatures(self):
        return []

    def is_class(self):
        return False

    def is_instance(self):
        return False

    def is_function(self):
        return False

    def is_module(self):
        return False

    def is_namespace(self):
        return False

    def is_compiled(self):
        return False

    def is_bound_method(self):
        return False

    def py__bool__(self):
        """
        Since Wrapper is a super class for classes, functions and modules,
        the return value will always be true.
        """
        return True

    def py__doc__(self):
        try:
            self.tree_node.get_doc_node
        except AttributeError:
            return ''
        else:
            return clean_scope_docstring(self.tree_node)
        return None

    def get_safe_value(self, default=_sentinel):
        if default is _sentinel:
            raise ValueError("There exists no safe value for value %s" % self)
        return default

    def py__call__(self, arguments):
        debug.warning("no execution possible %s", self)
        return NO_VALUES

    def py__stop_iteration_returns(self):
        debug.warning("Not possible to return the stop iterations of %s", self)
        return NO_VALUES

    def get_qualified_names(self):
        # Returns Optional[Tuple[str, ...]]
        return None

    def is_stub(self):
        # The root value knows if it's a stub or not.
        return self.parent_value.is_stub()


def iterate_values(values, valueualized_node=None, is_async=False):
    """
    Calls `iterate`, on all values but ignores the ordering and just returns
    all values that the iterate functions yield.
    """
    return ContextSet.from_sets(
        lazy_value.infer()
        for lazy_value in values.iterate(valueualized_node, is_async=is_async)
    )


class _ContextWrapperBase(HelperContextMixin):
    predefined_names = {}

    @safe_property
    def name(self):
        from jedi.inference.names import ContextName
        wrapped_name = self._wrapped_value.name
        if wrapped_name.tree_name is not None:
            return ContextName(self, wrapped_name.tree_name)
        else:
            from jedi.inference.compiled import CompiledContextName
            return CompiledContextName(self, wrapped_name.string_name)

    @classmethod
    @infer_state_as_method_param_cache()
    def create_cached(cls, infer_state, *args, **kwargs):
        return cls(*args, **kwargs)

    def __getattr__(self, name):
        assert name != '_wrapped_value', 'Problem with _get_wrapped_value'
        return getattr(self._wrapped_value, name)


class LazyContextWrapper(_ContextWrapperBase):
    @safe_property
    @memoize_method
    def _wrapped_value(self):
        with debug.increase_indent_cm('Resolve lazy value wrapper'):
            return self._get_wrapped_value()

    def __repr__(self):
        return '<%s>' % (self.__class__.__name__)

    def _get_wrapped_value(self):
        raise NotImplementedError


class ContextWrapper(_ContextWrapperBase):
    def __init__(self, wrapped_value):
        self._wrapped_value = wrapped_value

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._wrapped_value)


class TreeContext(Context):
    def __init__(self, infer_state, parent_value, tree_node):
        super(TreeContext, self).__init__(infer_state, parent_value)
        self.predefined_names = {}
        self.tree_node = tree_node

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.tree_node)


class ContextualizedNode(object):
    def __init__(self, value, node):
        self.value = value
        self.node = node

    def get_root_value(self):
        return self.value.get_root_value()

    def infer(self):
        return self.value.infer_node(self.node)

    def __repr__(self):
        return '<%s: %s in %s>' % (self.__class__.__name__, self.node, self.value)


class ContextualizedName(ContextualizedNode):
    # TODO merge with TreeNameDefinition?!
    @property
    def name(self):
        return self.node

    def assignment_indexes(self):
        """
        Returns an array of tuple(int, node) of the indexes that are used in
        tuple assignments.

        For example if the name is ``y`` in the following code::

            x, (y, z) = 2, ''

        would result in ``[(1, xyz_node), (0, yz_node)]``.

        When searching for b in the case ``a, *b, c = [...]`` it will return::

            [(slice(1, -1), abc_node)]
        """
        indexes = []
        is_star_expr = False
        node = self.node.parent
        compare = self.node
        while node is not None:
            if node.type in ('testlist', 'testlist_comp', 'testlist_star_expr', 'exprlist'):
                for i, child in enumerate(node.children):
                    if child == compare:
                        index = int(i / 2)
                        if is_star_expr:
                            from_end = int((len(node.children) - i) / 2)
                            index = slice(index, -from_end)
                        indexes.insert(0, (index, node))
                        break
                else:
                    raise LookupError("Couldn't find the assignment.")
                is_star_expr = False
            elif node.type == 'star_expr':
                is_star_expr = True
            elif isinstance(node, (ExprStmt, SyncCompFor)):
                break

            compare = node
            node = node.parent
        return indexes


def _getitem(value, index_values, valueualized_node):
    from jedi.inference.value.iterable import Slice

    # The actual getitem call.
    simple_getitem = getattr(value, 'py__simple_getitem__', None)

    result = NO_VALUES
    unused_values = set()
    for index_value in index_values:
        if simple_getitem is not None:
            index = index_value
            if isinstance(index_value, Slice):
                index = index.obj

            try:
                method = index.get_safe_value
            except AttributeError:
                pass
            else:
                index = method(default=None)

            if type(index) in (float, int, str, unicode, slice, bytes):
                try:
                    result |= simple_getitem(index)
                    continue
                except SimpleGetItemNotFound:
                    pass

        unused_values.add(index_value)

    # The index was somehow not good enough or simply a wrong type.
    # Therefore we now iterate through all the values and just take
    # all results.
    if unused_values or not index_values:
        result |= value.py__getitem__(
            ContextSet(unused_values),
            valueualized_node
        )
    debug.dbg('py__getitem__ result: %s', result)
    return result


class ContextSet(BaseContextSet):
    def py__class__(self):
        return ContextSet(c.py__class__() for c in self._set)

    def iterate(self, valueualized_node=None, is_async=False):
        from jedi.inference.lazy_value import get_merged_lazy_value
        type_iters = [c.iterate(valueualized_node, is_async=is_async) for c in self._set]
        for lazy_values in zip_longest(*type_iters):
            yield get_merged_lazy_value(
                [l for l in lazy_values if l is not None]
            )

    def execute(self, arguments):
        return ContextSet.from_sets(c.infer_state.execute(c, arguments) for c in self._set)

    def execute_with_values(self, *args, **kwargs):
        return ContextSet.from_sets(c.execute_with_values(*args, **kwargs) for c in self._set)

    def py__getattribute__(self, *args, **kwargs):
        if kwargs.get('is_goto'):
            return reduce(add, [c.py__getattribute__(*args, **kwargs) for c in self._set], [])
        return ContextSet.from_sets(c.py__getattribute__(*args, **kwargs) for c in self._set)

    def get_item(self, *args, **kwargs):
        return ContextSet.from_sets(_getitem(c, *args, **kwargs) for c in self._set)

    def try_merge(self, function_name):
        value_set = self.__class__([])
        for c in self._set:
            try:
                method = getattr(c, function_name)
            except AttributeError:
                pass
            else:
                value_set |= method()
        return value_set

    def gather_annotation_classes(self):
        return ContextSet.from_sets([c.gather_annotation_classes() for c in self._set])

    def get_signatures(self):
        return [sig for c in self._set for sig in c.get_signatures()]


NO_VALUES = ContextSet([])


def iterator_to_value_set(func):
    def wrapper(*args, **kwargs):
        return ContextSet(func(*args, **kwargs))

    return wrapper
