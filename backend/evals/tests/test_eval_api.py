from typing import Any

import pytest
from django.test import Client

from accounts.models import User
from evals import run_compare, scoring
from evals.models import EvalResult, EvalRun

pytestmark = pytest.mark.django_db

BASE = "/api/workbench/eval"


@pytest.fixture
def signed_in(client: Client, db: None) -> Client:
    client.force_login(User.objects.create_user("s@example.com", is_staff=True))
    return client


def make_run(
    target: str = "traces", model: str = "gemini-3.5-flash", **kw: Any
) -> EvalRun:
    return EvalRun.objects.create(
        target=target, provider="gemini", model=model, prompt_version="v1", **kw
    )


def add(
    run: EvalRun, outcomes: dict[str, str], cluster: dict[str, str] | None = None
) -> EvalRun:
    for qid, outcome in outcomes.items():
        EvalResult.objects.create(
            run=run,
            question_id=qid,
            question=f"q {qid}",
            gold_sql="SELECT 1",
            predicted_sql="SELECT 2",
            outcome=outcome,
            cluster_key=(cluster or {}).get(qid, ""),
            input_tokens=1000,
            output_tokens=500,
        )
    run.question_count = run.results.count()
    run.correct_count = run.results.filter(outcome="correct").count()
    run.status = "done"
    run.save()
    return run


def test_the_list_filters_and_shows_accuracy_and_cost(signed_in: Client) -> None:
    a = add(make_run(), {"1": "correct", "2": "wrong"})
    add(make_run(target="olist", model="other"), {"1": "correct"})
    body = signed_in.get(f"{BASE}/runs?target=traces").json()
    assert [r["id"] for r in body["data"]] == [a.pk]
    row = body["data"][0]
    assert row["accuracy"] == 0.5 and row["question_count"] == 2
    # 2 results x (1000 in, 500 out) at 0.30 / 2.50 USD per million, per question
    assert row["cost_per_question_usd"] == pytest.approx(0.00155)
    assert len(signed_in.get(f"{BASE}/runs?model=other").json()["data"]) == 1
    assert signed_in.get(f"{BASE}/runs?runner=agent").json()["data"] == []


def test_the_detail_has_results_links_and_cluster_accuracy(signed_in: Client) -> None:
    run = add(
        make_run(),
        {"1": "correct", "2": "wrong", "3": "correct"},
        {"1": "answered/a", "2": "answered/a", "3": "error/b"},
    )
    data = signed_in.get(f"{BASE}/runs/{run.pk}").json()
    body = data["data"]
    assert len(body["results"]) == 3 and data["meta"]["count"] == 3
    assert body["results"][0]["gold_sql"] == "SELECT 1"
    by = {c["cluster_key"]: c for c in body["by_cluster"]}
    assert by["answered/a"]["accuracy"] == 0.5 and by["error/b"]["accuracy"] == 1.0
    assert signed_in.get(f"{BASE}/runs/99999").status_code == 404


def test_the_numbers_match_the_step_2_report(signed_in: Client) -> None:
    run = add(
        make_run(), {str(n): "correct" if n % 3 else "wrong" for n in range(1, 11)}
    )
    summary = scoring.summarise(run)
    row = signed_in.get(f"{BASE}/runs/{run.pk}").json()["data"]
    assert row["accuracy"] == pytest.approx(summary.accuracy)
    assert row["correct_count"] == summary.correct
    assert f"{summary.accuracy:.1%}" in scoring.format_report(run)


def test_compare_lists_flips_both_ways_and_cluster_changes(signed_in: Client) -> None:
    cluster = {"1": "a", "2": "a", "3": "b", "4": "b"}
    base = add(
        make_run(),
        {"1": "correct", "2": "wrong", "3": "correct", "4": "correct", "5": "wrong"},
        cluster,
    )
    other = add(
        make_run(model="m2"),
        {"1": "wrong", "2": "correct", "3": "correct", "4": "correct", "6": "correct"},
        cluster,
    )
    data = signed_in.get(f"{BASE}/compare?base={base.pk}&other={other.pk}").json()[
        "data"
    ]
    assert (
        data["shared"] == 4 and data["only_in_base"] == 1 and data["only_in_other"] == 1
    )
    flips = {f["question_id"]: f["direction"] for f in data["flips"]}
    assert flips == {"1": "to_wrong", "2": "to_correct"}
    assert data["base_accuracy"] == 0.75 and data["other_accuracy"] == 0.75
    assert data["diff_points"] == 0
    assert {c["cluster_key"]: c["diff_points"] for c in data["clusters"]} == {
        "a": 0.0,
        "b": 0.0,
    }


def test_compare_shows_a_drop(signed_in: Client) -> None:
    base = add(make_run(), {"1": "correct", "2": "correct"})
    other = add(make_run(), {"1": "correct", "2": "wrong"})
    data = signed_in.get(f"{BASE}/compare?base={base.pk}&other={other.pk}").json()[
        "data"
    ]
    assert data["diff_points"] == -50.0
    assert data["clusters"][0]["cluster_key"] == run_compare.UNCLUSTERED


def test_runs_of_different_targets_are_refused(signed_in: Client) -> None:
    a = add(make_run(), {"1": "correct"})
    b = add(make_run(target="olist"), {"1": "correct"})
    response = signed_in.get(f"{BASE}/compare?base={a.pk}&other={b.pk}")
    assert response.status_code == 422
    assert response.json()["code"] == "eval_runs_not_comparable"
    assert signed_in.get(f"{BASE}/compare?base={a.pk}&other=999").status_code == 404
