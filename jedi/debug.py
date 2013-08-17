from _compatibility import u, encoding, is_py3k
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

# callback, interface: level, str
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
            debug_function(NOTICE, 'dbg: ' + ', '.join(u(a) for a in args))


def warning(*args):
    if debug_function and enable_warning:
        debug_function(WARNING, 'warning: ' + ', '.join(u(a) for a in args))


def speed(name):
    if debug_function and enable_speed:
        now = time.time()
        debug_function(SPEED, 'speed: ' + '%s %s' % (name, now - start_time))


def print_to_stdout(level, str_out):
    """ The default debug function """
    if level == NOTICE:
        col = Fore.GREEN
    elif level == WARNING:
        col = Fore.RED
    else:
        col = Fore.YELLOW
    if not is_py3k:
        str_out = str_out.encode(encoding, 'replace')
    print(col + str_out + Fore.RESET)


# debug_function = print_to_stdout
