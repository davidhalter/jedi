def simple(a):
    return a

simple(1)
#! 6 type-error-too-few-arguments
simple()
#! 10 type-error-too-many-arguments
simple(1, 2)


def nested(*args):
    # TODO: shoult not be her but in line 17
    #! 13 type-error-too-few-arguments
    return simple(*args)

nested(1)
nested()
#! 10 type-error-too-many-arguments
simple(1, 2, 3)
