"""
Makes it possible to do the compiled analysis in a subprocess. This has two
goals:

1. Making it safer - Segfaults and RuntimeErrors as well as stdout/stderr can
   be ignored and dealt with.
2. Make it possible to handle different Python versions as well as virtualenvs.
"""

import os
import sys
import subprocess
import weakref
import pickle
import types
from functools import partial

from jedi.cache import memoize_method
from jedi.evaluate.compiled.subprocess import functions
from jedi.evaluate.compiled import CompiledObject

_PICKLE_PROTOCOL = 2

_subprocesses = {}

_MAIN_PATH = os.path.join(os.path.dirname(__file__), '__main__.py')


def get_subprocess(executable):
    try:
        return _subprocesses[executable]
    except KeyError:
        sub = _subprocesses[executable] = _CompiledSubprocess(executable)
        return sub


def _get_function(name):
    return getattr(functions, name)


class EvaluatorSameProcess(object):
    """
    Basically just an easy access to functions.py. It has the same API
    as EvaluatorSubprocess and does the same thing without using a subprocess.
    This is necessary for the Interpreter process.
    """
    def __init__(self, evaluator):
        self._evaluator = evaluator

    def __getattr__(self, name):
        return partial(_get_function(name), self._evaluator, IgnoreHandles())


class EvaluatorSubprocess(object):
    def __init__(self, evaluator, compiled_subprocess):
        self._used = False
        self._evaluator_weakref = weakref.ref(evaluator)
        self._evaluator_id = id(evaluator)
        self._compiled_subprocess = compiled_subprocess

    def __getattr__(self, name):
        func = _get_function(name)

        def wrapper(*args, **kwargs):
            self._used = True

            result = self._compiled_subprocess.run(
                self._evaluator_weakref(),
                func,
                args=args,
                kwargs=kwargs,
                unpickler=lambda stdout: ModifiedUnpickler(self, stdout).load()
            )
            if isinstance(result, CompiledHandle):
                result.add_subprocess(self)

            return result

        return wrapper

    def __del__(self):
        if self._used:
            self._compiled_subprocess.delete_evaluator(self._evaluator_id)


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
            # stderr=subprocess.PIPE
        )

    def _send(self, evaluator_id, function, args=(), kwargs={}, unpickler=pickle.load):
        data = evaluator_id, function, args, kwargs
        pickle.dump(data, self._process.stdin, protocol=_PICKLE_PROTOCOL)
        self._process.stdin.flush()
        is_exception, result = unpickler(self._process.stdout)
        if is_exception:
            raise result
        return result

    def terminate(self):
        self._process.terminate()

    def kill(self):
        self._process.kill()


class _CompiledSubprocess(_Subprocess):
    def __init__(self, executable):
        parso_path = sys.modules['parso'].__file__
        super(_CompiledSubprocess, self).__init__(
            (executable,
             _MAIN_PATH,
             os.path.dirname(os.path.dirname(parso_path))
             )
        )

    def run(self, evaluator, function, args=(), kwargs={}, unpickler=None):
        assert callable(function)
        return self._send(id(evaluator), function, args, kwargs, unpickler=unpickler)

    def get_sys_path(self):
        return self._send(None, functions.get_sys_path, (), {})

    def delete_evaluator(self, evaluator_id):
        # With an argument - the evaluator gets deleted.
        self._send(evaluator_id, None)


class Listener():
    def __init__(self):
        self._evaluators = {}

    def _get_evaluator(self, function, evaluator_id):
        from jedi.evaluate import Evaluator, project

        try:
            evaluator, handles = self._evaluators[evaluator_id]
        except KeyError:
            evaluator = Evaluator(None, project=project.Project())
            handles = Handles()
            self._evaluators[evaluator_id] = evaluator, handles
        return evaluator, handles

    def _run(self, evaluator_id, function, args, kwargs):
        print(function, args, kwargs, file=sys.stderr)
        if evaluator_id is None:
            return function(*args, **kwargs)
        elif function is None:
            del self._evaluators[evaluator_id]
        else:
            evaluator, handles = self._get_evaluator(function, evaluator_id)
            return function(evaluator, handles, *args, **kwargs)

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
            try:
                result = False, self._run(*payload)
            except Exception as e:
                result = True, e

            ModifiedPickler(stdout, protocol=_PICKLE_PROTOCOL).dump(result)
            stdout.flush()


class ModifiedUnpickler(pickle._Unpickler):
    dispatch = pickle._Unpickler.dispatch.copy()

    def __init__(self, subprocess, *args, **kwargs):
        super(ModifiedUnpickler, self).__init__(*args, **kwargs)
        self._subprocess = subprocess

    def load_inst(self):
        raise NotImplementedError
    dispatch[pickle.INST[0]] = load_inst

    def load_obj(self):
        raise NotImplementedError
    dispatch[pickle.OBJ[0]] = load_obj
    dispatch = pickle._Unpickler.dispatch.copy()

    def load_newobj(self):
        super(ModifiedUnpickler, self).load_newobj()
        tos = self.stack[-1]
        if isinstance(tos, CompiledHandle):
            tos.add_subprocess(self._subprocess)
        print('pop', tos, file=sys.stderr)
    dispatch[pickle.NEWOBJ[0]] = load_newobj

    def load_newobj_ex(self):
        super(ModifiedUnpickler, self).load_newobj_ex()
        tos = self.stack[-1]
        print('popex', tos, file=sys.stderr)
    dispatch[pickle.NEWOBJ_EX[0]] = load_newobj_ex

    def _instantiate(self, klass, k):
        super(ModifiedUnpickler, self)._instantiate(klass, k)
        tos = self.stack[-1]
        print('tttt', tos)


class ModifiedPickler(pickle._Pickler):
    def save(self, obj, *args, **kwargs):
        print('s', obj, args, kwargs, file=sys.stderr)
        if isinstance(obj, CompiledObject):
            obj = CompiledHandle(obj)
        return super(ModifiedPickler, self).save(obj, *args, **kwargs)


class Handles(object):
    def __init__(self):
        self._handles = {}

    def create(self, obj):
        handle = self._handles[id(obj)] = CompiledHandle(obj)
        return handle

    def get_compiled_object(self, id_):
        return self._handles[id_].compiled_object


class IgnoreHandles(object):
    def create(self, obj):
        return obj


class CompiledHandle(object):
    def __init__(self, compiled_object):
        self.compiled_object = compiled_object
        self._id = id(compiled_object)

    @property
    def obj(self):
        raise NotImplementedError

    def add_subprocess(self, subprocess):
        self._subprocess = subprocess

    def __getstate__(self):
        return self._id

    def __setstate__(self, state):
        self._id = state

    def __getattr__(self, name):
        from jedi.evaluate import compiled
        attr = getattr(compiled.CompiledObject, name)
        if isinstance(attr, property):
            return self._subprocess.get_compiled_property(self._id, name)
        elif isinstance(attr, compiled.CheckAttribute):
            # It might raise an AttributeError, however we're interested in the
            # function return value.
            self._subprocess.get_compiled_property(self._id, name)

        def compiled_method(*args, **kwargs):
            return self._subprocess.get_compiled_method_return(self._id, name, *args, **kwargs)
        return compiled_method
