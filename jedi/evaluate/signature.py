from abc import abstractproperty


class AbstractSignature(object):
    def __init__(self, is_bound=False):
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
        param_names = self.function_context.get_param_names()
        if self.is_bound:
            return param_names[1:]
        return param_names


class TreeSignature(AbstractSignature):
    def __init__(self, function_context, is_bound=False):
        super(TreeSignature, self).__init__(is_bound)
        self.function_context = function_context

    @property
    def name(self):
        name = self.function_context.name
        if name.string_name == '__init__':
            try:
                class_context = self.function_context.class_context
            except AttributeError:
                pass
            else:
                return class_context.name
        return name

    def bind(self):
        return TreeSignature(self.function_context, is_bound=True)

    def annotation(self):
        return self.function_context.tree_node.annotation

    def to_string(self, normalize=False):
        return self.function_context.tree_node


class BuiltinSignature(AbstractSignature):
    def __init__(self, compiled_obj, is_bound=False):
        super(BuiltinSignature, self).__init__(is_bound=is_bound)
        self.function_context = compiled_obj

    def bind(self):
        raise NotImplementedError('pls implement, need test case')
