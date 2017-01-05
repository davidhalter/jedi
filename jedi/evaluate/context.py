from jedi._compatibility import Python3Method
from jedi.common import unite


class Context(object):
    api_type = None
    """
    To be defined by subclasses.
    """
    predefined_names = {}
    tree_node = None

    def __init__(self, evaluator, parent_context=None):
        self.evaluator = evaluator
        self.parent_context = parent_context

    def get_parent_flow_context(self):
        return self.parent_context

    def get_root_context(self):
        context = self
        while True:
            if context.parent_context is None:
                return context
            context = context.parent_context

    def execute(self, arguments):
        return self.evaluator.execute(self, arguments)

    def execute_evaluated(self, *value_list):
        """
        Execute a function with already executed arguments.
        """
        from jedi.evaluate.param import ValuesArguments
        arguments = ValuesArguments([[value] for value in value_list])
        return self.execute(arguments)

    def eval_node(self, node):
        return self.evaluator.eval_element(self, node)

    def eval_stmt(self, stmt, seek_name=None):
        return self.evaluator.eval_statement(self, stmt, seek_name)

    @Python3Method
    def eval_trailer(self, types, trailer):
        return self.evaluator.eval_trailer(self, types, trailer)

    @Python3Method
    def py__getattribute__(self, name_or_str, name_context=None, position=None,
                           search_global=False, is_goto=False):
        if name_context is None:
            name_context = self
        return self.evaluator.find_types(
            self, name_or_str, name_context, position, search_global, is_goto)

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


class TreeContext(Context):
    def __init__(self, evaluator, parent_context=None):
        super(TreeContext, self).__init__(evaluator, parent_context)
        self.predefined_names = {}

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.tree_node)


class FlowContext(TreeContext):
    def get_parent_flow_context(self):
        if 1:
            return self.parent_context


class AbstractLazyContext(object):
    def __init__(self, data):
        self.data = data

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self.data)

    def infer(self):
        raise NotImplementedError


class LazyKnownContext(AbstractLazyContext):
    """data is a context."""
    def infer(self):
        return set([self.data])


class LazyKnownContexts(AbstractLazyContext):
    """data is a set of contexts."""
    def infer(self):
        return self.data


class LazyUnknownContext(AbstractLazyContext):
    def __init__(self):
        super(LazyUnknownContext, self).__init__(None)

    def infer(self):
        return set()


class LazyTreeContext(AbstractLazyContext):
    def __init__(self, context, node):
        super(LazyTreeContext, self).__init__(node)
        self._context = context
        # We need to save the predefined names. It's an unfortunate side effect
        # that needs to be tracked otherwise results will be wrong.
        self._predefined_names = dict(context.predefined_names)

    def infer(self):
        old, self._context.predefined_names = \
            self._context.predefined_names, self._predefined_names
        try:
            return self._context.eval_node(self.data)
        finally:
            self._context.predefined_names = old


def get_merged_lazy_context(lazy_contexts):
    if len(lazy_contexts) > 1:
        return MergedLazyContexts(lazy_contexts)
    else:
        return lazy_contexts[0]


class MergedLazyContexts(AbstractLazyContext):
    """data is a list of lazy contexts."""
    def infer(self):
        return unite(l.infer() for l in self.data)
