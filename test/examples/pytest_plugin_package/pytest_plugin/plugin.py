import pytest
from pytest import fixture


from pytest_plugin.fixtures import admin_user  # noqa


class Client:
    def login(self, **credentials):
        ...

    def logout(self):
        ...


@pytest.fixture()
def admin_client():
    return Client()
