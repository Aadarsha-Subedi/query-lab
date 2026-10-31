import pytest

from accounts.models import User


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user("ada@example.com")


@pytest.fixture
def other_user(db: None) -> User:
    return User.objects.create_user("grace@example.com")
