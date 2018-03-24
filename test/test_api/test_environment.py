import os
import sys
from contextlib import contextmanager

import pytest

import jedi
from jedi._compatibility import py_version
from jedi.api.environment import Environment, get_default_environment, \
    InvalidPythonEnvironment, find_python_environments


def test_sys_path():
    assert get_default_environment().get_sys_path()


def test_find_python_environments():
    envs = list(find_python_environments())
    assert len(envs)
    for env in envs:
        assert env.version_info
        assert env.get_sys_path()
        parser_version = env.get_grammar().version_info
        assert parser_version[:2] == env.version_info[:2]


# Cannot deduce the environment from Python executable name on Windows.
@pytest.mark.skipif("os.name == 'nt'")
@pytest.mark.parametrize(
    'version',
    ['2.7', '3.3', '3.4', '3.5', '3.6', '3.7']
)
def test_versions(version):
    executable = 'python' + version
    try:
        env = Environment('some path', executable)
    except InvalidPythonEnvironment:
        if int(version.replace('.', '')) == py_version:
            # At least the current version has to work
            raise
        return

    sys_path = env.get_sys_path()
    assert any(executable in p for p in sys_path)


def test_load_module(evaluator):
    access_path = evaluator.compiled_subprocess.load_module(
        name=u'math',
        sys_path=evaluator.get_sys_path()
    )
    name, access_handle = access_path.accesses[0]

    assert access_handle.py__bool__() is True
    assert access_handle.get_api_type() == 'module'
    with pytest.raises(AttributeError):
        access_handle.py__mro__()


def test_error_in_environment(evaluator, Script):
    # Provoke an error to show how Jedi can recover from it.
    with pytest.raises(jedi.InternalError):
        evaluator.compiled_subprocess._test_raise_error(KeyboardInterrupt)
    # The second time it should raise an InternalError again.
    with pytest.raises(jedi.InternalError):
        evaluator.compiled_subprocess._test_raise_error(KeyboardInterrupt)
    # Jedi should still work.
    def_, = Script('str').goto_definitions()
    assert def_.name == 'str'


def test_stdout_in_subprocess(evaluator, Script):
    evaluator.compiled_subprocess._test_print(stdout='.')
    Script('1').goto_definitions()


def test_killed_subprocess(evaluator, Script):
    # Just kill the subprocess.
    evaluator.compiled_subprocess._compiled_subprocess._process.kill()
    # Since the process was terminated (and nobody knows about it) the first
    # Jedi call fails.
    with pytest.raises(jedi.InternalError):
        Script('str').goto_definitions()

    def_, = Script('str').goto_definitions()
    # Jedi should now work again.
    assert def_.name == 'str'


@contextmanager
def set_environment_variable(name, value):
    tmp = os.environ.get(name)
    try:
        os.environ[name] = value
        yield
    finally:
        if tmp is None:
            del os.environ[name]
        else:
            os.environ[name] = tmp


def test_virtualenv():
    with set_environment_variable('VIRTUAL_ENV', '/foo/bar/jedi_baz'):
        assert get_default_environment()._executable == sys.executable
