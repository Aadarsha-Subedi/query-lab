import pytest

from accounts.models import User
from agent.models import AgentRun
from ask.schema import Column, ForeignKey, Schema, Table


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


@pytest.fixture
def schema() -> Schema:
    """A hand-built slice of the Olist schema; order_status has sample values."""
    return Schema(
        name="demo",
        tables=(
            Table(
                name="orders",
                comment="Customer orders.",
                columns=(
                    Column("order_id", "text", False, "Order id."),
                    Column("customer_id", "text", True, None),
                    Column(
                        "order_status",
                        "text",
                        True,
                        "Where the order is.",
                        samples=("delivered", "shipped", "canceled", "created"),
                    ),
                    Column(
                        "order_purchase_timestamp",
                        "timestamp without time zone",
                        True,
                        None,
                    ),
                ),
                primary_key=("order_id",),
                foreign_keys=(
                    ForeignKey(("customer_id",), "customers", ("customer_id",)),
                ),
                row_estimate=99441,
            ),
            Table(
                name="customers",
                comment=None,
                columns=(
                    Column("customer_id", "text", False, None),
                    Column("customer_state", "text", True, None),
                ),
                primary_key=("customer_id",),
            ),
        ),
    )
