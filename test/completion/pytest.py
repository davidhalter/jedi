# python > 2
import pytest
from pytest import fixture


@pytest.fixture(scope='module')
def my_fixture() -> str:
    pass


@fixture
def my_simple_fixture():
    return 1


# -----------------
# goto/infer
# -----------------

#! 18 'def my_conftest_fixture'
def test_x(my_conftest_fixture, my_fixture, my_not_existing_fixture):
    #? str()
    my_fixture
    #?
    my_not_existing_fixture
    #? float()
    return my_conftest_fixture

#? 18 float()
def test_x(my_conftest_fixture, my_fixture):
    pass

# -----------------
# completion
# -----------------

#? 34 ['my_fixture']
def test_x(my_simple_fixture, my_fixture):
    return
#? 18 ['my_simple_fixture']
def test_x(my_simple_fixture):
    return
#? 18 ['my_conftest_fixture']
def test_x(my_conftest_fixture):
    return
