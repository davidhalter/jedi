class AbstractSignature(object):
    def __init__(self, context, is_bound=False):
        self.context = context
        self.is_bound = is_bound

    @property
    def name(self):
        return self.context.name

    @property
    def annotation(self):
        return None

    def to_string(self):
        param_code = ', '.join(n.to_string() for n in self.get_param_names())
        s = self.name.string_name + '(' + param_code + ')'
        annotation = self.annotation
        if annotation is not None:
                s += ' -> ' + annotation.get_code(include_prefix=False)
        return s

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

    @property
    def annotation(self):
        # Classes don't need annotations, even if __init__ has one. They always
        # return themselves.
        if self.context.is_class():
            return None
        return self._function_context.tree_node.annotation


class BuiltinSignature(AbstractSignature):
    @property
    def _function_context(self):
        return self.context

    def to_string(self):
        return self.name.string_name + self.context.get_signature_text()

    def bind(self, context):
        raise NotImplementedError('pls implement, need test case, %s' % context)
