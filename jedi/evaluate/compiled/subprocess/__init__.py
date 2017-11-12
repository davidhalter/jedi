"""
Makes it possible to do the compiled analysis in a subprocess. This has two
goals:

1. Making it safer - Segfaults and RuntimeErrors as well as stdout/stderr can
   be ignored and dealt with.
2. Make it possible to handle different Python versions as well as virtualenvs.
"""

import sys
import subprocess
import pickle

_PICKLE_PROTOCOL = 2


class _SubProcess(object):
    def __init__(self, args):
        self._process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            #stderr=subprocess.PIPE
        )

    def _send(self, data):
        pickle.dump(data, self._process.stdin, protocol=_PICKLE_PROTOCOL)
        self._process.stdin.flush()
        return pickle.load(self._process.stdout)

    def terminate(self):
        self._process.terminate()

    def kill(self):
        self._process.kill()


class CompiledSubProcess(object):
    def __init__(self, executable):
        super(CompiledSubProcess, self).__init__(
            (executable, '-m', 'jedi.evaluate.compiled.subprocess')
        )

    def command(self, command):
        return self._send()


def listen():
    stdout = sys.stdout
    stdin = sys.stdin
    if sys.version_info[0] > 2:
        stdout = stdout.buffer
        stdin = stdin.buffer

    while True:
        try:
            result = pickle.load(stdin)
        except EOFError:
            # It looks like the parent process closed. Don't make a big fuss
            # here and just exit.
            exit(1)
        result += 1
        pickle.dump(result, stdout, protocol=_PICKLE_PROTOCOL)
        stdout.flush()
