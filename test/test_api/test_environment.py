from jedi.api.virtualenv import Environment, DefaultEnvironment


def test_sys_path():
    assert DefaultEnvironment('/foo').get_sys_path()
