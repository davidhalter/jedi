from jedi.parser import Parser

def test_get_code():
    """Use the same code that the parser also generates, to compare"""
    s = \
'''"""a docstring"""
class SomeClass(object, mixin):
    def __init__(self):
        self.xy = 3.0
        """statement docstr"""
    def some_method(self):
        return 1
    def yield_method(self):
        while hasattr(self, 'xy'):
            yield True
        for x in [1, 2]:
            yield x
    def empty(self):
        pass
class Empty:
    pass
class WithDocstring:
    """class docstr"""
    pass
def method_with_docstring():
    """class docstr"""
    pass
'''
    assert Parser(s).module.get_code() == s
