
def simple(a):
    return a


def nested(*args):
    return simple(*args)

nested(1)
#! 6 type-error-too-few-arguments
nested()


def nested_no_call_to_function(*args):
    return simple(1, *args)
