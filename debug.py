import inspect

def dbg(*args):
    if debug_function:
        frm =  inspect.stack()[1]
        mod = inspect.getmodule(frm[0])
        if not (mod.__name__ in ignored_modules):
            debug_function(*args)

def warning(*args):
    if debug_function:
        debug_function(*args)

debug_function = None
ignored_modules = []
