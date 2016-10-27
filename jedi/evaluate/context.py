class Context(object):
    type = None # TODO remove

    def __init__(self, evaluator, parent_context=None):
        self._evaluator = evaluator
        self.parent_context = parent_context

    def get_parent_flow_context(self):
        return self.parent_context

    def get_root_context(self):
        context = self
        while True:
            if context.parent_context is None:
                return context
            context = context.parent_context

    def execute(self, arguments=None):
        return self._evaluator.execute(self, arguments)

    def execute_evaluated(self, *value_list):
        """
        Execute a function with already executed arguments.
        """
        from jedi.evaluate.param import ValueArguments
        return self.execute(ValueArguments(value_list))


class TreeContext(Context):
    def eval_node(self, node):
        return self._evaluator.eval_element(self, node)


class FlowContext(TreeContext):
    def get_parent_flow_context(self):
        if 1:
            return self.parent_context
