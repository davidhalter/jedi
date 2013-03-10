from os.path import join, dirname, abspath
default_base_dir = join(dirname(abspath(__file__)), 'completion')

import run


def pytest_addoption(parser):
    parser.addoption(
        "--base-dir", default=default_base_dir,
        help="Directory in which integration test case files locate.")
    parser.addoption(
        "--test-files", "-T", default=[], action='append',
        help=(
            "Specify test files using FILE_NAME[:LINE[,LINE[,...]]]. "
            "For example: -T generators.py:10,13,19. "
            "Note that you can use -m to specify the test case by id."))
    parser.addoption(
        "--thirdparty",
        help="Include integration tests that requires third party modules.")


def parse_test_files_option(opt):
    """
    Parse option passed to --test-files into a key-value pair.

    >>> parse_test_files_option('generators.py:10,13,19')
    ('generators.py', [10, 13, 19])
    """
    opt = str(opt)
    if ':' in opt:
        (f_name, rest) = opt.split(':', 1)
        return (f_name, list(map(int, rest.split(','))))
    else:
        return (opt, [])


def pytest_generate_tests(metafunc):
    """
    :type metafunc: _pytest.python.Metafunc
    """
    if 'case' in metafunc.fixturenames:
        base_dir = metafunc.config.option.base_dir
        test_files = dict(map(parse_test_files_option,
                              metafunc.config.option.test_files))
        thirdparty = metafunc.config.option.thirdparty
        metafunc.parametrize(
            'case',
            run.collect_dir_tests(base_dir, test_files, thirdparty))
