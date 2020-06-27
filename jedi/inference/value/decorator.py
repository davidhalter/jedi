'''
Decorators are not really values, however we need some wrappers to improve
docstrings and other things around decorators.
'''

from jedi.inference.base_value import ValueWrapper, ValueSet
from jedi.inference.names import ValueName
from jedi.inference.signature import SignatureWrapper


class Decoratee(ValueWrapper):
    def __init__(self, wrapped_value, original_value):
        super(Decoratee, self).__init__(wrapped_value)
        self._original_value = original_value

    def py__doc__(self):
        return self._original_value.py__doc__()

    def py__get__(self, instance, class_value):
        return ValueSet(
            Decoratee(v, self._original_value)
            for v in self._wrapped_value.py__get__(instance, class_value)
        )

    @property
    def name(self):
        if self._wrapped_value.is_function():
            # If a function is returned, the name that we want is usually the
            # original one. This is obviously a bit weird, but it works pretty
            # well, since users don't pass around functions randomly.
            val = self._original_value
        else:
            val = self._wrapped_value

        if val.name.tree_name is not None:
            return ValueName(self, val.name.tree_name)
        return self._wrapped_value.name

    def get_signatures(self):
        return [DecorateeSignature(sig, self.name)
                for sig in self._wrapped_value.get_signatures()]


class DecorateeSignature(SignatureWrapper):
    def __init__(self, signature, name):
        super(DecorateeSignature, self).__init__(signature)
        self.name = name
