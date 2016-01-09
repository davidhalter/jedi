from jedi._compatibility import encoding, is_py3, u
import inspect
import os
import time

try:
    if os.name == 'nt':
        # does not work on Windows, as pyreadline and colorama interfere
        raise ImportError
    else:
        # Use colorama for nicer console output.
        from colorama import Fore, init
        from colorama import initialise
        # pytest resets the stream at the end - causes troubles. Since after
        # every output the stream is reset automatically we don't need this.
        initialise.atexit_done = True
        init()
except ImportError:
    class Fore(object):
        RED = ''
        GREEN = ''
        YELLOW = ''
        MAGENTA = ''
        RESET = ''

NOTICE = object()
WARNING = object()
SPEED = object()

enable_speed = False
enable_warning = False
enable_notice = False

# callback, interface: level, str
debug_function = None
ignored_modules = ['jedi.parser']
_debug_indent = 0
_start_time = time.time()


def reset_time():
    global _start_time, _debug_indent
    _start_time = time.time()
    _debug_indent = 0


def increase_indent(func):
    """Decorator for makin """
    def wrapper(*args, **kwargs):
        global _debug_indent
        _debug_indent += 1
        try:
            return func(*args, **kwargs)
        finally:
            _debug_indent -= 1
    return wrapper


def dbg(message, *args, **kwargs):
    """ Looks at the stack, to see if a debug message should be printed. """
    if kwargs:
        # Python 2 compatibility, because it doesn't understand default args
        # after *args.
        color = kwargs.get('color')
        if color is None:
            raise TypeError("debug.dbg doesn't support more named arguments than color")
    else:
        color = 'GREEN'

    if debug_function and enable_notice:
        frm = inspect.stack()[1]
        mod = inspect.getmodule(frm[0])
        if not (mod.__name__ in ignored_modules):
            i = ' ' * _debug_indent
            debug_function(color, i + 'dbg: ' + message % tuple(u(repr(a)) for a in args))


def warning(message, *args):
    if debug_function and enable_warning:
        i = ' ' * _debug_indent
        debug_function('RED', i + 'warning: ' + message % tuple(u(repr(a)) for a in args))


def speed(name):
    if debug_function and enable_speed:
        now = time.time()
        i = ' ' * _debug_indent
        debug_function('YELLOW', i + 'speed: ' + '%s %s' % (name, now - _start_time))


def print_to_stdout(color, str_out):
    """
    The default debug function that prints to standard out.

    :param str color: A string that is an attribute of ``colorama.Fore``.
    """
    col = getattr(Fore, color)
    if not is_py3:
        str_out = str_out.encode(encoding, 'replace')
    print(col + str_out + Fore.RESET)


# debug_function = print_to_stdout
