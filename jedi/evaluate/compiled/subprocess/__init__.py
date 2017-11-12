"""
Makes it possible to do the compiled analysis in a subprocess. This has two
goals:

1. Making it safer - Segfaults and RuntimeErrors as well as stdout/stderr can
   be ignored and dealt with.
2. Make it possible to handle different Python versions as well as virtualenvs.
"""

import sys
import subprocess
import weakref
import pickle
from functools import partial

from jedi.cache import memoize_method
from jedi.evaluate.compiled.subprocess import commands

_PICKLE_PROTOCOL = 2

_subprocesses = {}


def get_subprocess(executable):
    try:
        return _subprocesses[executable]
    except KeyError:
        sub = _subprocesses[executable] = _CompiledSubprocess(executable)
        return sub


class EvaluatorSameProcess(object):
    """
    Basically just an easy access to functions.py. It has the same API
    as EvaluatorSubprocess and does the same thing without using a subprocess.
    This is necessary for the Interpreter process.
    """
    def __init__(self, evaluator):
        self._evaluator = evaluator

    def __getattr__(self):
        function = getattr(commands, name)
        return partial(function, self._evaluator)


class EvaluatorSubprocess(object):
    def __init__(self, evaluator, compiled_subprocess):
        self._evaluator_weakref = weakref.ref(evaluator)
        self._evaluator_id = ()
        self._compiled_subprocess = compiled_subprocess

    def __getattr__(self, name):
        function = getattr(commands, name)
        return partial(function, self._evaluator_weakref())

    def __del__(self):
        self.delete_evaluator(self._evaluator_weakref()


class _Subprocess(object):
    def __init__(self, args):
        self._args = args

    @property
    @memoize_method
    def _process(self):
        return subprocess.Popen(
            self._args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            #stderr=subprocess.PIPE
        )

    def _send(self, *data):
        pickle.dump(data, self._process.stdin, protocol=_PICKLE_PROTOCOL)
        self._process.stdin.flush()
        return pickle.load(self._process.stdout)

    def terminate(self):
        self._process.terminate()

    def kill(self):
        self._process.kill()


class _CompiledSubprocess(_Subprocess):
    def __init__(self, executable):
        super(_CompiledSubprocess, self).__init__(
            (executable, '-m', 'jedi.evaluate.compiled.subprocess')
        )

    def run(self, evaluator, function, *args, **kwargs):
        assert callable(function)
        return self._send(id(evaluator), function, args, kwargs)

    def delete_evaluator(self, evaluator_id):
        # With an argument - the evaluator gets deleted.
        self._send(evaluator_id, None)


class Listener():
    def __init__(self):
        self._evaluators = {}

    def _run(self, evaluator_id, function, args, kwargs):
        from jedi.evaluate import Evaluator

        if function is None:
            # If the function is None, this is the hint to delete the
            # evaluator.
            del self._evaluators[evaluator_id]
            return

        try:
            evaluator = self.evaluators[evaluator_id]
        except KeyError:
            evaluator = Evaluator(None, None)
            self.evaluators[evaluator_id] = evaluator

        return function(evaluator, *args, **kwargs)

    def listen(self):
        stdout = sys.stdout
        stdin = sys.stdin
        if sys.version_info[0] > 2:
            stdout = stdout.buffer
            stdin = stdin.buffer

        while True:
            try:
                payload = pickle.load(stdin)
            except EOFError:
                # It looks like the parent process closed. Don't make a big fuss
                # here and just exit.
                exit(1)
            result = self._run(*payload)
            pickle.dump(result, stdout, protocol=_PICKLE_PROTOCOL)
            stdout.flush()
