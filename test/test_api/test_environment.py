import os
from contextlib import contextmanager

import pytest

import jedi
from jedi._compatibility import py_version
from jedi.api.environment import get_default_environment, find_virtualenvs, \
    InvalidPythonEnvironment, find_system_environments, get_system_environment


def test_sys_path():
    assert get_default_environment().get_sys_path()


def test_find_system_environments():
    envs = list(find_system_environments())
    assert len(envs)
    for env in envs:
        assert env.version_info
        assert env.get_sys_path()
        parser_version = env.get_grammar().version_info
        assert parser_version[:2] == env.version_info[:2]


@pytest.mark.parametrize(
    'version',
    ['2.7', '3.3', '3.4', '3.5', '3.6', '3.7']
)
def test_versions(version):
    try:
        env = get_system_environment(version)
    except InvalidPythonEnvironment:
        if int(version.replace('.', '')) == py_version:
            # At least the current version has to work
            raise
        pytest.skip()

    assert version == str(env.version_info[0]) + '.' + str(env.version_info[1])
    assert env.get_sys_path()


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


def test_not_existing_virtualenv():
    """Should not match the path that was given"""
    path = '/foo/bar/jedi_baz'
    with set_environment_variable('VIRTUAL_ENV', path):
        assert get_default_environment().executable != path


def test_working_venv(venv_path):
    with set_environment_variable('VIRTUAL_ENV', venv_path):
        assert get_default_environment().path == venv_path


def test_scanning_venvs(venv_path):
    parent_dir = os.path.dirname(venv_path)
    assert any(venv.path == venv_path for venv in find_virtualenvs([parent_dir]))
