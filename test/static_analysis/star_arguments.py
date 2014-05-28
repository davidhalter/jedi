
def simple(a):
    return a

def nested(*args):
    return simple(*args)

nested(1)
#! 6 type-error-too-few-arguments
nested()
