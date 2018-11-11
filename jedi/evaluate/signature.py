from abc import abstractproperty


class AbstractSignature(object):
    def __init__(self, context, is_bound=False):
        self._context = context
        self.is_bound = is_bound

    @abstractproperty
    def name(self):
        raise NotImplementedError

    def annotation(self):
        return None

    def to_string(self):
        raise NotImplementedError

    def bind(self):
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

    @property
    def name(self):
        name = self._function_context.name
        if name.string_name == '__init__':
            try:
                class_context = self._function_context.class_context
            except AttributeError:
                pass
            else:
                return class_context.name
        return name

    def bind(self, context):
        return TreeSignature(context, self._function_context, is_bound=True)

    def annotation(self):
        return self._function_context.tree_node.annotation

    def to_string(self, normalize=False):
        return self._function_context.tree_node


class BuiltinSignature(AbstractSignature):
    @property
    def _function_context(self):
        return self._context

    def bind(self):
        raise NotImplementedError('pls implement, need test case')
