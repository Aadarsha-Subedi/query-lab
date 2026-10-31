import json
from typing import Any

import pytest
from django.utils import timezone

from accounts.models import User
from common.llm import LLMRequest, LLMResponse
from common.llm.base import LLMProvider, LLMRateLimitedError
from evals import drafting
from evals.models import TraceCase

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]

GOOD = "SELECT count(*) AS n FROM orders"


class Scripted(LLMProvider):
    provider = "gemini"
    model = "draft-model"

    def __init__(self, replies: list[Any]) -> None:
        self.replies = list(replies)
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return LLMResponse(reply, self.model, 1, 1)

    def validate_key(self) -> None:
        return None


def answer(sql: str, answerable: bool = True) -> str:
    return json.dumps(
        {"answerable": answerable, "sql": sql, "rationale": "r", "self_confidence": 0.5}
    )


def make_case(n: int = 1, reasons: str = "failed", source_sql: str = "") -> TraceCase:
    return TraceCase.objects.create(
        source_run_id=n,
        source_created_at=timezone.now(),
        question=f"How many orders {n}?",
        reasons=reasons,
        signals=len(reasons.split(",")),
        outcome="error",
        source_sql=source_sql,
    )


@pytest.fixture
def user(db: None) -> User:
    return User.objects.create_user("staff@example.com", is_staff=True)


def test_a_good_draft_is_guarded_run_and_stored() -> None:
    case = make_case()
    drafting.draft_case(case, Scripted([answer(GOOD)]), "SCHEMA")
    case.refresh_from_db()
    assert case.status == "drafted" and case.draft_error == ""
    assert "orders" in case.draft_sql and "LIMIT" in case.draft_sql.upper()
    assert case.draft_model == "draft-model" and case.gold_sql == ""


@pytest.mark.parametrize(
    ("sql", "fragment"),
    [("DELETE FROM orders", ""), ("SELECT nope FROM orders", "")],
)
def test_a_bad_draft_is_stored_with_its_error(sql: str, fragment: str) -> None:
    case = make_case()
    drafting.draft_case(case, Scripted([answer(sql)]), "SCHEMA")
    case.refresh_from_db()
    assert case.status == "drafted" and case.draft_error
    assert case.gold_sql == ""


def test_a_declined_draft_keeps_the_reason() -> None:
    case = make_case()
    drafting.draft_case(case, Scripted([answer("", answerable=False)]), "S")
    case.refresh_from_db()
    assert case.status == "drafted" and case.draft_error.startswith("declined")


def test_a_provider_failure_leaves_a_candidate_to_retry() -> None:
    case = make_case()
    drafting.draft_case(case, Scripted([LLMRateLimitedError()]), "S")
    case.refresh_from_db()
    assert case.status == "candidate" and case.draft_error == "llm_rate_limited"


def test_the_prompt_has_question_schema_and_edited_sql_but_no_rows() -> None:
    case = make_case(reasons="edited,failed", source_sql="SELECT 7")
    text = drafting.build_draft_prompt(case, "SCHEMA TEXT")
    assert "How many orders 1?" in text and "SCHEMA TEXT" in text
    assert "<approved_sql>\nSELECT 7" in text
    plain = drafting.build_draft_prompt(make_case(2, source_sql="SELECT 7"), "S")
    assert "SELECT 7" not in plain


def test_a_batch_is_capped_and_counts_the_default_key(
    user: User, settings: Any
) -> None:
    settings.TRACES_DRAFT_MAX_PER_BATCH = 2
    for n in range(1, 5):
        make_case(n)
    provider = Scripted([answer(GOOD)] * 2)
    assert drafting.draft_batch(user, provider) == 2
    assert len(provider.requests) == 2
    assert TraceCase.objects.filter(status="candidate").count() == 2


def test_a_batch_stops_when_the_key_limit_is_used_up(user: User, settings: Any) -> None:
    settings.ASK_DEFAULT_KEY_DAILY_LIMIT = 1
    make_case(1)
    make_case(2)
    provider = Scripted([answer(GOOD)] * 2)
    assert drafting.draft_batch(user, provider) == 1
    assert len(provider.requests) == 1
