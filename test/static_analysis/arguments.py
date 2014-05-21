def simple(a):
    return a

simple(1)
simple()
#! 10 type-error-too-many-params
simple(1, 2)


def nested(*args):
    return simple(*args)

nested(1)
nested()
#! 10 type-error-too-many-params
simple(1, 2, 3)
