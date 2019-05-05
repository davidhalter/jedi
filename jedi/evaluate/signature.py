from jedi.parser_utils import get_call_signature


class AbstractSignature(object):
    def __init__(self, context, is_bound=False):
        self.context = context
        self.is_bound = is_bound

    @property
    def name(self):
        return self.context.name

    def annotation(self):
        return None

    def to_string(self):
        raise NotImplementedError

    def bind(self, context):
        raise NotImplementedError

    def get_param_names(self):
        param_names = self._function_context.get_param_names()
        if self.is_bound:
            return param_names[1:]
        return param_names


class TreeSignature(AbstractSignature):
    def __init__(self, context, function_context=None, is_bound=False):
        super(TreeSignature, self).__init__(context, is_bound)
        self._function_context = function_context or context

    def bind(self, context):
        return TreeSignature(context, self._function_context, is_bound=True)

    def annotation(self):
        return self._function_context.tree_node.annotation

    def to_string(self, normalize=False):
        return get_call_signature(
            self._function_context.tree_node,
            call_string=self.name.string_name,
        )


class BuiltinSignature(AbstractSignature):
    @property
    def _function_context(self):
        return self.context

    def to_string(self):
        return ''

    def bind(self, context):
        raise NotImplementedError('pls implement, need test case, %s' % context)
