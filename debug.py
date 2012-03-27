
def dbg(*args):
    if debug_function:
        debug_function(*args)


debug_function = None
