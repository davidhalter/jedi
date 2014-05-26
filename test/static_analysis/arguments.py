# -----------------
# normal arguments (no keywords)
# -----------------


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

# -----------------
# keyword arguments
# -----------------

simple(a=1)
#! 7 type-error-keyword-argument
simple(b=1)
#! 10 type-error-too-many-arguments
simple(1, a=1)


def two_params(x, y):
    return y


two_params(y=2, x=1)
two_params(1, y=2)

# The next two statements should generate errors. Basically it should generate
# something like `TypeError: x() got multiple values for keyword argument 'a'`.
# For now however, any error should be fine.
two_params(1, x=2)
#! 17 type-error-too-many-arguments
two_params(1, 2, y=3)
