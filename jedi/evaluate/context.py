from jedi.common import unite


class Context(object):
    type = None # TODO remove
    api_type = 'instance'
    """
    Most contexts are just instances of something, therefore make this the
    default to make subclassing a lot easier.
    """

    def __init__(self, evaluator, parent_context=None):
        self.evaluator = evaluator
        self.parent_context = parent_context

    def get_node(self):
        return None

    def get_parent_flow_context(self):
        return self.parent_context

    def get_root_context(self):
        context = self
        while True:
            if context.parent_context is None:
                return context
            context = context.parent_context

    def execute(self, arguments=None):
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


class TreeContext(Context):
    pass
class FlowContext(TreeContext):
    def get_parent_flow_context(self):
        if 1:
            return self.parent_context


class AbstractLazyContext(object):
    def __init__(self, data):
        self._data = data

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self._data)

    def infer(self):
        raise NotImplementedError


class LazyKnownContext(AbstractLazyContext):
    """data is a context."""
    def infer(self):
        yield self._data


class LazyKnownContexts(AbstractLazyContext):
    """data is a set of contexts."""
    def infer(self):
        return self._data


class LazyUnknownContext(AbstractLazyContext):
    def __init__(self):
        super(LazyUnknownContext, self).__init__(None)

    def infer(self):
        return set()


class LazyTreeContext(AbstractLazyContext):
    def __init__(self, context, node):
        self._context = context
        self._data = node

    def infer(self):
        return self._context.eval_node(self._data)


def get_merged_lazy_context(lazy_contexts):
    if len(lazy_contexts) > 1:
        return MergedLazyContexts(lazy_contexts)
    else:
        return lazy_contexts[0]


class MergedLazyContexts(AbstractLazyContext):
    """data is a list of lazy contexts."""
    def infer(self):
        return unite(l.infer() for l in self._data)
