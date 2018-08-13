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


class Context(BaseContext):
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


def _get_item(context, index_contexts, contextualized_node):
    from jedi.evaluate.compiled import CompiledObject
    from jedi.evaluate.context.iterable import Slice, Sequence

    # The actual getitem call.
    simple_getitem = getattr(context, 'py__simple_getitem__', None)
    getitem = getattr(context, 'py__getitem__', None)

    if getitem is None and simple_getitem is None:
        from jedi.evaluate import analysis
        # TODO this context is probably not right.
        analysis.add(
            contextualized_node.context,
            'type-error-not-subscriptable',
            contextualized_node.node,
            message="TypeError: '%s' object is not subscriptable" % context
        )
        return NO_CONTEXTS

    result = ContextSet()
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

        # The index was somehow not good enough or simply a wrong type.
        # Therefore we now iterate through all the contexts and just take
        # all results.
        if getitem is not None:
            result |= getitem(index_context, contextualized_node)
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
        return ContextSet.from_sets(_get_item(c, *args, **kwargs) for c in self._set)


NO_CONTEXTS = ContextSet()


def iterator_to_context_set(func):
    def wrapper(*args, **kwargs):
        return ContextSet.from_iterable(func(*args, **kwargs))

    return wrapper
