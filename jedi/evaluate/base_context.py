"""
Contexts are the "values" that Python would return. However Contexts are at the
same time also the "contexts" that a user is currently sitting in.

A ContextSet is typically used to specify the return of a function or any other
static analysis operation. In jedi there are always multiple returns and not
just one.
"""
from parso.python.tree import ExprStmt, CompFor

from jedi import debug
from jedi._compatibility import Python3Method, zip_longest, unicode
from jedi.parser_utils import clean_scope_docstring, get_doc_with_call_signature
from jedi.common import BaseContextSet, BaseContext
from jedi.evaluate.helpers import SimpleGetItemNotFound, execute_evaluated
from jedi.evaluate.utils import safe_property
from jedi.evaluate.cache import evaluator_as_method_param_cache


def _is_same_class(class1, class2):
    if class1 == class2:
        return True

    try:
        comp_func = class1.is_same_class
    except AttributeError:
        try:
            comp_func = class2.is_same_class
        except AttributeError:
            return False
        else:
            return comp_func(class1)
    else:
        return comp_func(class2)


class HelperContextMixin:
    @classmethod
    @evaluator_as_method_param_cache()
    def create_cached(cls, *args, **kwargs):
        return cls(*args, **kwargs)

    def execute_evaluated(self, *value_list):
        return execute_evaluated(self, *value_list)

    @Python3Method
    def py__getattribute__(self, name_or_str, name_context=None, position=None,
                           search_global=False, is_goto=False,
                           analysis_errors=True):
        """
        :param position: Position of the last statement -> tuple of line, column
        """
        if name_context is None:
            name_context = self
        from jedi.evaluate import finder
        f = finder.NameFinder(self.evaluator, self, name_context, name_or_str,
                              position, analysis_errors=analysis_errors)
        filters = f.get_filters(search_global)
        if is_goto:
            return f.filter_name(filters)
        return f.find(filters, attribute_lookup=not search_global)

    def is_sub_class_of(self, class_context):
        from jedi.evaluate.context.klass import py__mro__
        for cls in py__mro__(self):
            if _is_same_class(cls, class_context):
                return True
        return False


class Context(HelperContextMixin, BaseContext):
    """
    Should be defined, otherwise the API returns empty types.
    """

    predefined_names = {}
    tree_node = None
    """
    To be defined by subclasses.
    """

    @property
    def api_type(self):
        # By default just lower name of the class. Can and should be
        # overwritten.
        return self.__class__.__name__.lower()

    def iterate(self, contextualized_node=None, is_async=False):
        debug.dbg('iterate %s', self)
        try:
            if is_async:
                iter_method = self.py__aiter__
            else:
                iter_method = self.py__iter__
        except AttributeError:
            if contextualized_node is not None:
                from jedi.evaluate import analysis
                analysis.add(
                    contextualized_node.context,
                    'type-error-not-iterable',
                    contextualized_node.node,
                    message="TypeError: '%s' object is not iterable" % self)
            return iter([])
        else:
            return iter_method()

    def eval_node(self, node):
        return self.evaluator.eval_element(self, node)

    def py__getitem__(self, index_context_set, contextualized_node):
        from jedi.evaluate import analysis
        # TODO this context is probably not right.
        analysis.add(
            contextualized_node.context,
            'type-error-not-subscriptable',
            contextualized_node.node,
            message="TypeError: '%s' object is not subscriptable" % self
        )
        return NO_CONTEXTS

    def execute_annotation(self):
        return execute_evaluated(self)

    def create_context(self, node, node_is_context=False, node_is_object=False):
        return self.evaluator.create_context(self, node, node_is_context, node_is_object)

    def is_class(self):
        return False

    def py__bool__(self):
        """
        Since Wrapper is a super class for classes, functions and modules,
        the return value will always be true.
        """
        return True

    def py__doc__(self, include_call_signature=False):
        try:
            self.tree_node.get_doc_node
        except AttributeError:
            return ''
        else:
            if include_call_signature:
                return get_doc_with_call_signature(self.tree_node)
            else:
                return clean_scope_docstring(self.tree_node)
        return None


def iterate_contexts(contexts, contextualized_node=None, is_async=False):
    """
    Calls `iterate`, on all contexts but ignores the ordering and just returns
    all contexts that the iterate functions yield.
    """
    return ContextSet.from_sets(
        lazy_context.infer()
        for lazy_context in contexts.iterate(contextualized_node, is_async=is_async)
    )


class ContextWrapper(HelperContextMixin, object):
    py__getattribute__ = Context.py__getattribute__

    def __init__(self, wrapped_context):
        self._wrapped_context = wrapped_context

    @safe_property
    def name(self):
        from jedi.evaluate.filters import ContextName
        wrapped_name = self._wrapped_context.name
        if wrapped_name.tree_name is not None:
            return ContextName(self, wrapped_name.tree_name)
        else:
            from jedi.evaluate.compiled import CompiledContextName
            return CompiledContextName(self, wrapped_name.string_name)

    def __getattr__(self, name):
        return getattr(self._wrapped_context, name)

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self._wrapped_context)


class TreeContext(Context):
    def __init__(self, evaluator, parent_context, tree_node):
        super(TreeContext, self).__init__(evaluator, parent_context)
        self.predefined_names = {}
        self.tree_node = tree_node

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.tree_node)


class ContextualizedNode(object):
    def __init__(self, context, node):
        self.context = context
        self.node = node

    def get_root_context(self):
        return self.context.get_root_context()

    def infer(self):
        return self.context.eval_node(self.node)

    def __repr__(self):
        return '<%s: %s in %s>' % (self.__class__.__name__, self.node, self.context)


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
        """
        indexes = []
        node = self.node.parent
        compare = self.node
        while node is not None:
            if node.type in ('testlist', 'testlist_comp', 'testlist_star_expr', 'exprlist'):
                for i, child in enumerate(node.children):
                    if child == compare:
                        indexes.insert(0, (int(i / 2), node))
                        break
                else:
                    raise LookupError("Couldn't find the assignment.")
            elif isinstance(node, (ExprStmt, CompFor)):
                break

            compare = node
            node = node.parent
        return indexes


def _getitem(context, index_contexts, contextualized_node):
    from jedi.evaluate.compiled import CompiledObject
    from jedi.evaluate.context.iterable import Slice

    # The actual getitem call.
    simple_getitem = getattr(context, 'py__simple_getitem__', None)

    result = ContextSet()
    unused_contexts = set()
    for index_context in index_contexts:
        if simple_getitem is not None:
            index = index_context
            if isinstance(index_context, Slice):
                index = index.obj
            if isinstance(index, CompiledObject):
                try:
                    index = index.get_safe_value()
                except ValueError:
                    pass

            if type(index) in (float, int, str, unicode, slice, bytes):
                try:
                    result |= simple_getitem(index)
                    continue
                except SimpleGetItemNotFound:
                    pass

        unused_contexts.add(index_context)

    # The index was somehow not good enough or simply a wrong type.
    # Therefore we now iterate through all the contexts and just take
    # all results.
    if unused_contexts or not index_contexts:
        result |= context.py__getitem__(
            ContextSet.from_set(unused_contexts),
            contextualized_node
        )
    debug.dbg('py__getitem__ result: %s', result)
    return result


class ContextSet(BaseContextSet):
    def py__class__(self):
        return ContextSet.from_iterable(c.py__class__() for c in self._set)

    def iterate(self, contextualized_node=None, is_async=False):
        from jedi.evaluate.lazy_context import get_merged_lazy_context
        type_iters = [c.iterate(contextualized_node, is_async=is_async) for c in self._set]
        for lazy_contexts in zip_longest(*type_iters):
            yield get_merged_lazy_context(
                [l for l in lazy_contexts if l is not None]
            )

    def execute(self, arguments):
        return ContextSet.from_sets(c.evaluator.execute(c, arguments) for c in self._set)

    def execute_evaluated(self, *args, **kwargs):
        return ContextSet.from_sets(execute_evaluated(c, *args, **kwargs) for c in self._set)

    def get_item(self, *args, **kwargs):
        return ContextSet.from_sets(_getitem(c, *args, **kwargs) for c in self._set)

    def is_sub_class_of(self, class_context):
        for c in self._set:
            if c.is_sub_class_of(class_context):
                return True
        return False


NO_CONTEXTS = ContextSet()


def iterator_to_context_set(func):
    def wrapper(*args, **kwargs):
        return ContextSet.from_iterable(func(*args, **kwargs))

    return wrapper
