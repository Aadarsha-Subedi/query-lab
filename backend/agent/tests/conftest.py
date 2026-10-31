from collections.abc import Iterator

import pytest

from accounts.models import User
from agent.models import AgentRun
from ask.schema import Column, ForeignKey, Schema, Table
from common.redis import get_redis


@pytest.fixture(autouse=True)
def _clean_agent_keys() -> Iterator[None]:
    """Run state, locks and event streams live in Redis; start each test empty."""
    client = get_redis()
    for key in client.scan_iter("agent:*"):
        client.delete(key)
    yield
    for key in client.scan_iter("agent:*"):
        client.delete(key)


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


# ── a scripted agent: fake LLM, fake schema, fake runner ──────────────────

import json  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402

from ask import keys, runner  # noqa: E402
from ask import schema as schema_module  # noqa: E402
from common.llm.fake import FakeProvider  # noqa: E402


def plan_reply(*steps: str, assumptions: tuple[str, ...] = ()) -> str:
    return json.dumps(
        {"plan": list(steps) or ["look", "propose"], "assumptions": list(assumptions)}
    )


def tool_reply(name: str, **tool_input: object) -> str:
    return json.dumps({"tool": name, "input": tool_input})


def reflect_reply(
    verdict: str = "ok", reason: str = "fine", revised_sql: str = ""
) -> str:
    return json.dumps(
        {"verdict": verdict, "reason": reason, "revised_sql": revised_sql}
    )


PROPOSE = tool_reply(
    "propose_sql",
    sql="SELECT order_status, count(*) AS n FROM demo.orders GROUP BY 1",
    rationale="count by status",
)

TWO_BY_TWO = runner.QueryResult(
    columns=["order_status", "n"],
    rows=[["delivered", 5], ["shipped", 2]],
    row_count=2,
    truncated=False,
)


@dataclass
class Scripted:
    """The pieces a loop test controls: LLM answers, and what the database returns."""

    llm: FakeProvider
    executed: list[str] = field(default_factory=list)
    results: list[object] = field(default_factory=list)

    def answers(self, *replies: str) -> None:
        self.llm.answers.extend(replies)

    def returns(self, *results: object) -> None:
        """Queue results; an exception instance is raised instead of returned."""
        self.results.extend(results)


@pytest.fixture
def scripted(monkeypatch: pytest.MonkeyPatch, schema: Schema) -> Scripted:
    fake = FakeProvider(model="fake-model")
    script = Scripted(llm=fake)
    monkeypatch.setattr(
        keys,
        "resolve_provider",
        lambda user: keys.ResolvedProvider(fake, "gemini", keys.KEY_DEFAULT),
    )
    monkeypatch.setattr(schema_module, "get_schema", lambda *a, **k: schema)

    def fake_run(
        sql: str, workspace: object = None, **kwargs: object
    ) -> runner.QueryResult:
        script.executed.append(sql)
        outcome = script.results.pop(0) if script.results else TWO_BY_TWO
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # type: ignore[return-value]

    monkeypatch.setattr(runner, "run", fake_run)
    return script
