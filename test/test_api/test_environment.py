import pytest

import jedi
from jedi._compatibility import py_version
from jedi.api.virtualenv import Environment, DefaultEnvironment, NoVirtualEnv


def test_sys_path():
    assert DefaultEnvironment('/foo').get_sys_path()


@pytest.mark.parametrize(
    'version',
    # TODO add '2.6', '2.7',
    ['3.3', '3.4', '3.5', '3.6', '3.7']
)
def test_versions(version):
    executable = 'python' + version
    try:
        env = Environment('some path', executable)
    except NoVirtualEnv:
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
