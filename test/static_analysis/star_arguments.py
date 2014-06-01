# -----------------
# *args
# -----------------


def simple(a):
    return a


def nested(*args):
    return simple(*args)

nested(1)
#! 6 type-error-too-few-arguments
nested()


def nested_no_call_to_function(*args):
    return simple(1, *args)


def simple2(a, b, c):
    return b
def nested(*args):
    return simple2(1, *args)
def nested_twice(*args1):
    return nested(*args1)

nested_twice(2, 3)
#! 12 type-error-too-few-arguments
nested_twice(2)
#! 19 type-error-too-many-arguments
nested_twice(2, 3, 4)

# -----------------
# **kwargs
# -----------------


def kwargs_test(**kwargs):
    return simple2(1, **kwargs)

kwargs_test(c=3, b=2)
#! 11 type-error-too-few-arguments
kwargs_test(c=3)
#! 11 type-error-too-few-arguments
kwargs_test(b=2)
#! 22 type-error-keyword-argument
kwargs_test(b=2, c=3, d=4)
#! 22 type-error-multiple-values
kwargs_test(b=2, c=3, a=4)
