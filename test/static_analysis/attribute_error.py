class Cls():
    class_attr = ''
    def __init__(self, input):
        self.instance_attr = 3
        self.input = input

    def f(self):
        #! attribute-error
        return self.not_existing

    def undefined_object(self, obj):
        """
        Uses an arbitrary object and performs an operation on it, shouldn't
        be a problem.
        """
        obj.arbitrary_lookup

    def defined_lookup(self, obj):
        """
        `obj` is defined by a call into this function.
        """
        obj.upper
        #! attribute-error
        obj.arbitrary_lookup

    #! attribute-error
    class_attr = a

Cls().defined_lookup('')

c = Cls()
c.class_attr
Cls.class_attr
#! attribute-error
Cls.class_attr_error
c.instance_attr
#! attribute-error
c.instance_attr_error


c.something = None
