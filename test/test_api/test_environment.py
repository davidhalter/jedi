import pytest

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
        parser_version = env.get_parser().version_info
        assert parser_version[:2] == env.version_info[:2]


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
    access_path = evaluator.compiled_subprocess.load_module(name='math')
    name, access_handle = access_path.accesses[0]

    assert access_handle.py__bool__() is True
    assert access_handle.get_api_type() == 'module'
    with pytest.raises(AttributeError):
        access_handle.py__mro__()
