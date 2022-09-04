import pytest

from .fixtures import admin_user  # noqa


@pytest.fixture()
def admin_client():
    return Client()


class Client:
    def login(self, **credentials):
        ...

    def logout(self):
        ...
