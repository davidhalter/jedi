import inspect
import time

try:
    # Use colorama for nicer console output.
    from colorama import Fore, init
    init()
except ImportError:
    class Fore(object):
        RED = ''
        GREEN = ''
        YELLOW = ''
        RESET = ''

NOTICE = object()
WARNING = object()
SPEED = object()

enable_speed = False
enable_warning = False
enable_notice = False

debug_function = None
ignored_modules = ['parsing', 'builtin', 'jedi.builtin', 'jedi.parsing']


def reset_time():
    global start_time
    start_time = time.time()


def dbg(*args):
    """ Looks at the stack, to see if a debug message should be printed. """
    if debug_function and enable_notice:
        frm = inspect.stack()[1]
        mod = inspect.getmodule(frm[0])
        if not (mod.__name__ in ignored_modules):
            debug_function(NOTICE, *args)


def warning(*args):
    if debug_function and enable_warning:
        debug_function(WARNING, *args)


def speed(name):
    if debug_function:
        args = ('%s\t\t' % name,)
        debug_function(SPEED, *args)


def print_to_stdout(level, *args):
    """ The default debug function """
    if level == NOTICE:
        msg = Fore.GREEN + 'dbg: '
    elif level == WARNING:
        msg = Fore.RED + 'warning: '
    else:
        msg = Fore.YELLOW + 'speed: '
    print(msg + ', '.join(str(a) for a in args) + Fore.RESET)


#debug_function = print_to_stdout
