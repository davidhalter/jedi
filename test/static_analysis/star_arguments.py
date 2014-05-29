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
