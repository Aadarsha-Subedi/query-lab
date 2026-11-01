"""The traces target: only approved cases, cluster recorded per result."""

import pytest
from django.utils import timezone

from evals import runner
from evals.models import EvalResult, EvalRun, TraceCase
from evals.targets.traces import TraceTarget
from evals.tests.conftest import ScriptedProvider, reply

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]

COUNT = "SELECT count(*) AS n FROM orders"
# Gold is stored as the guard wrote it: schema-qualified.
GOLD = "SELECT count(*) AS n FROM demo.orders"


def case(n: int, status: str, question: str, gold: str = GOLD, **fields) -> TraceCase:
    values = {
        "source_run_id": n,
        "source_created_at": timezone.now(),
        "question": question,
        "reasons": "failed",
        "outcome": "answered",
        "source_sql": gold or "",
        "status": status,
        "gold_sql": gold if status == "approved" else "",
    }
    values.update(fields)
    return TraceCase.objects.create(**values)


def run_traces(provider: ScriptedProvider, **kwargs) -> EvalRun:
    target = TraceTarget()
    return runner.run_eval(
        target,
        split="all",
        provider_name="gemini",
        provider=provider,
        questions=target.questions("all"),
        sleep=lambda seconds: None,
        **kwargs,
    )


def test_only_approved_cases_are_served() -> None:
    ok = case(1, "approved", "Count the orders")
    case(2, "drafted", "A drafted one", draft_sql=COUNT)
    case(3, "candidate", "A candidate")
    case(4, "rejected", "A rejected one")
    questions = TraceTarget().questions("all")
    assert [q.case_id for q in questions] == [ok.pk]
    assert questions[0].id == f"trace-{ok.pk}"
    assert questions[0].tags == questions[0].cluster != ""


def test_no_splits() -> None:
    with pytest.raises(ValueError):
        TraceTarget().questions("held-out")


def test_a_run_records_the_cluster_and_case_per_result() -> None:
    a = case(1, "approved", "Count the orders")
    case(
        2,
        "approved",
        "Count customers",
        gold="SELECT count(*) AS n FROM demo.customers",
    )
    run = run_traces(
        ScriptedProvider(
            lambda q: reply(
                COUNT if "orders" in q else "SELECT count(*) AS n FROM customers"
            )
        )
    )
    assert run.target == "traces" and run.question_count == 2 and run.correct_count == 2
    result = run.results.get(trace_case=a)
    a.refresh_from_db()
    assert result.cluster_key == a.cluster_key != ""
    assert result.tags == a.cluster_key
    assert run.results.values("cluster_key").distinct().count() == 2


def test_a_wrong_answer_is_scored_wrong() -> None:
    case(1, "approved", "Count the orders")
    run = run_traces(
        ScriptedProvider(lambda q: reply("SELECT 123456 AS n FROM orders"))
    )
    assert run.results.get().outcome == EvalResult.OUTCOME_WRONG


def test_an_unanswerable_case_means_decline() -> None:
    case(1, "approved", "What is the weather?", gold="", answerable=False)
    declined = run_traces(ScriptedProvider(lambda q: reply("", answerable=False)))
    assert declined.results.get().outcome == EvalResult.OUTCOME_CORRECT
    answered = run_traces(ScriptedProvider(lambda q: reply(COUNT)))
    assert answered.results.get().outcome == EvalResult.OUTCOME_WRONG
    assert answered.results.get().reason == "answered_unanswerable"


def test_the_model_never_sees_the_gold_sql() -> None:
    case(
        1,
        "approved",
        "Count the orders",
        gold="SELECT count(*) AS gold_marker FROM demo.orders",
    )
    provider = ScriptedProvider(lambda q: reply(COUNT))
    run_traces(provider)
    assert all("gold_marker" not in p for p in provider.prompts)
