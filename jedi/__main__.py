from sys import argv

if len(argv) == 2 and argv[1] == 'repl':
    # don't want to use __main__ only for repl yet, maybe we want to use it for
    # something else. So just use the keyword ``repl`` for now.
    from os import path
    print(path.join(path.dirname(path.abspath(__file__)), 'replstartup.py'))
