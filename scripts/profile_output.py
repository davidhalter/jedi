#!/usr/bin/env python
"""
Profile a piece of Python code with ``cProfile``. Tries a completion on a
certain piece of code.

Usage:
  profile.py [<code>] [-n <number>] [-d] [-o] [-s <sort>]
  profile.py -h | --help

Options:
  -h --help     Show this screen.
  -n <number>   Number of passes before profiling [default: 1].
  -d --debug    Enable Jedi internal debugging.
  -o --omit     Omit profiler, just do a normal run.
  -s <sort>     Sort the profile results, e.g. cum, name [default: time].
"""

import time
import cProfile

from docopt import docopt
import jedi


def run(code, index):
    start = time.time()
    result = jedi.Script(code).completions()
    print('Used %ss for the %sth run.' % (time.time() - start, index + 1))
    return result


def main(args):
    code = args['<code>']
    n = int(args['-n'])
    for i in range(n):
        run(code, i)

    jedi.set_debug_function(notices=args['--debug'])
    if args['--omit']:
        run(code, n)
    else:
        cProfile.runctx('run(code, n)', globals(), locals(), sort=args['-s'])


if __name__ == '__main__':
    args = docopt(__doc__)
    if args['<code>'] is None:
        args['<code>'] = 'import numpy; numpy.array([0]).'
    main(args)
