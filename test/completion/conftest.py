# Exists only for completion/pytest.py

import pytest


@pytest.fixture()
def my_other_conftest_fixture():
    return 1.0


@pytest.fixture()
def my_conftest_fixture(my_other_conftest_fixture):
    return my_other_conftest_fixture


def my_not_existing_fixture():
    return 3  # Just a normal function


@pytest.fixture()
def inheritance_fixture():
    return ''


@pytest.fixture
def capsysbinary(capsysbinary):
    #? ['close']
    capsysbinary.clos
    return capsysbinary


# used when fixtures are defined in multiple files
pytest_plugins = [
    "completion.fixture_module",
]
