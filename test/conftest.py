from os.path import join, dirname, abspath
default_base_dir = join(dirname(abspath(__file__)), 'completion')

import run


def pytest_addoption(parser):
    parser.addoption(
        "--base-dir", default=default_base_dir,
        help="Directory in which integration test case files locate.")
    parser.addoption(
        "--thirdparty",
        help="Include integration tests that requires third party modules.")


def pytest_generate_tests(metafunc):
    """
    :type metafunc: _pytest.python.Metafunc
    """
    if 'case' in metafunc.fixturenames:
        base_dir = metafunc.config.option.base_dir
        test_files = {}
        thirdparty = metafunc.config.option.thirdparty
        metafunc.parametrize(
            'case',
            run.collect_dir_tests(base_dir, test_files, thirdparty))
