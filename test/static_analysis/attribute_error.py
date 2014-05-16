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

    #! name-error
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

#! name-error
something = a
something

# -----------------
# Unused array variables should still raise attribute errors.
# -----------------

# should not raise anything.
for loop_variable in [1, 2]:
    #! name-error
    x = undefined
    loop_variable

#! name-error
for loop_variable in [1, 2, undefined]:
    pass

#! attribute-error
[1, ''.undefined_attr]


def return_one(something):
    return 1

#! attribute-error
return_one(''.undefined_attribute)

#! name-error
[r for r in undefined]

#! name-error
[undefined for r in [1, 2]]

[r for r in [1, 2]]
