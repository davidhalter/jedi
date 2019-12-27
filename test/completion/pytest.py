# python > 2
import pytest
from pytest import fixture


@pytest.fixture(scope='module')
def my_fixture() -> str:
    pass


@fixture
def my_simple_fixture():
    return 1


@fixture
def my_yield_fixture():
    yield 1


@fixture
class MyClassFixture():
    pass

# -----------------
# goto/infer
# -----------------

#! 18 ['def my_conftest_fixture']
def test_x(my_conftest_fixture, my_fixture, my_not_existing_fixture, my_yield_fixture):
    #? str()
    my_fixture
    #? int()
    my_yield_fixture
    #?
    my_not_existing_fixture
    #? float()
    return my_conftest_fixture

#? 18 float()
def test_x(my_conftest_fixture, my_fixture):
    pass


#! 18 ['param MyClassFixture']
def test_x(MyClassFixture):
    #?
    MyClassFixture

# -----------------
# completion
# -----------------

#? 34 ['my_fixture']
def test_x(my_simple_fixture, my_fixture):
    return
#? 34 ['my_fixture']
def test_x(my_simple_fixture, my_fixture):
    return
#? ['my_fixture']
def test_x(my_simple_fixture, my_f
    return
#? 18 ['my_simple_fixture']
def test_x(my_simple_fixture):
    return
#? ['my_simple_fixture']
def test_x(my_simp
    return
#? ['my_conftest_fixture']
def test_x(my_con
    return
#? 18 ['my_conftest_fixture']
def test_x(my_conftest_fixture):
    return
