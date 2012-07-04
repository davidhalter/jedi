import inspect
try:
    from colorama import Fore, init
    init()
except ImportError:
    class Fore(object):
        RED = ''
        GREEN = ''
        RESET = ''

NOTICE = object()
WARNING = object()
ERROR = object()


def dbg(*args):
    if debug_function:
        frm = inspect.stack()[1]
        mod = inspect.getmodule(frm[0])
        if not (mod.__name__ in ignored_modules):
            debug_function(NOTICE, *args)


def warning(*args):
    if debug_function:
        debug_function(WARNING, *args)


def error(*args):
    if debug_function:
        debug_function(ERROR, *args)


def print_to_stdout(level, *args):
    """ The default debug function """
    msg = (Fore.GREEN + 'dbg: ' if level == NOTICE else Fore.RED + 'warning: ')
    print(msg + ', '.join(str(a) for a in args) + Fore.RESET)


debug_function = None
#debug_function = print_to_stdout
ignored_modules = []
