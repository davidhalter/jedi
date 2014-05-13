from sys import argv
from os.path import join, dirname, abspath


if len(argv) == 2 and argv[1] == 'repl':
    # don't want to use __main__ only for repl yet, maybe we want to use it for
    # something else. So just use the keyword ``repl`` for now.
    print(join(dirname(abspath(__file__)), 'api', 'replstartup.py'))
elif len(argv) > 1 and argv[1] == 'force':
    import jedi
    import sys

    if '--debug' in sys.argv:
        jedi.set_debug_function()

    for error in jedi.Script(path=sys.argv[2])._analysis():
        print(error)
