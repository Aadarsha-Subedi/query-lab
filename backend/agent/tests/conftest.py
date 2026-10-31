import pytest

from accounts.models import User
from agent.models import AgentRun


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user("ada@example.com")


@pytest.fixture
def other_user(db: None) -> User:
    return User.objects.create_user("grace@example.com")


@pytest.fixture
def run(user: User) -> AgentRun:
    return AgentRun.objects.create(
        user=user,
        question="How many orders?",
        provider="gemini",
        model="fake-model",
        key_source="default",
        prompt_version="v2-agent",
    )
