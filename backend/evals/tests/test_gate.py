from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from evals import gate
from evals.models import EvalRun
from evals.tests.conftest import ScriptedProvider, reply
from evals.tests.test_eval_api import add, make_run
from evals.tests.test_traces_target import case

pytestmark = pytest.mark.django_db


def runs(
    base: dict[str, str], new: dict[str, str], **kw: Any
) -> tuple[EvalRun, EvalRun]:
    return add(make_run(**kw), base), add(make_run(**kw), new)


def verdict(
    base: EvalRun, new: EvalRun, drop: float = 2.0, cases: int = 1
) -> gate.Verdict:
    return gate.evaluate(new, base, max_drop_points=drop, min_cases=cases)


def ten(wrong: int) -> dict[str, str]:
    return {str(n): "wrong" if n < wrong else "correct" for n in range(10)}


def test_a_drop_at_the_threshold_passes_and_one_point_beyond_fails() -> None:
    base, at = runs(ten(0), ten(1))  # 10 points down
    assert verdict(base, at, drop=10.0).passed
    beyond = verdict(base, at, drop=9.0)
    assert not beyond.passed and beyond.reason == gate.DROPPED


def test_an_improvement_or_no_change_passes() -> None:
    base, better = runs(ten(2), ten(0))
    v = verdict(base, better, drop=0.0)
    assert v.passed and v.drop_points == -20.0
    base, same = runs(ten(1), ten(1))
    assert verdict(base, same, drop=0.0).passed


def test_flips_in_both_directions_are_listed() -> None:
    base, new = runs(
        {"a": "correct", "b": "wrong", "c": "correct"},
        {"a": "wrong", "b": "correct", "c": "correct"},
    )
    v = verdict(base, new, drop=100.0)
    assert {(f.question_id, f.direction) for f in v.flips} == {
        ("a", "to_wrong"),
        ("b", "to_correct"),
    }
    text = gate.format_verdict(v, new, base)
    assert "GATE PASSED" in text and "a to_wrong" in text and "b to_correct" in text


def test_a_dropping_cluster_is_reported() -> None:
    base = add(make_run(), {"1": "correct", "2": "correct"}, {"1": "x", "2": "y"})
    new = add(make_run(), {"1": "wrong", "2": "correct"}, {"1": "x", "2": "y"})
    assert [d.cluster_key for d in verdict(base, new, drop=100.0).cluster_drops] == [
        "x"
    ]


def test_too_few_shared_cases_fail_clearly() -> None:
    base, new = runs({"1": "correct"}, {"1": "correct"})
    v = verdict(base, new, cases=2)
    assert not v.passed and v.reason == gate.TOO_FEW_CASES
    assert "Too few shared cases" in gate.format_verdict(v, new, base)


def test_runs_of_different_targets_cannot_be_gated() -> None:
    a = add(make_run(), {"1": "correct"})
    b = add(make_run(target="olist"), {"1": "correct"})
    with pytest.raises(gate.NotComparable):
        gate.evaluate(b, a)


def test_the_latest_matching_baseline_is_found() -> None:
    old = add(make_run(), {"1": "correct"})
    newer = add(make_run(), {"1": "correct"})
    add(make_run(target="olist"), {"1": "correct"})
    candidate = add(make_run(), {"1": "correct"})
    assert gate.latest_baseline(candidate) == newer != old


@pytest.mark.usefixtures("data_connections")
class TestCommand:
    def run(self, answer: str, **options: Any) -> None:
        provider = ScriptedProvider(lambda q: reply(answer))
        import evals.runner as r

        original = r.build_provider
        r.build_provider = lambda model: ("gemini", provider)
        try:
            call_command(
                "run_eval", target="traces", model="gemini-3.5-flash", **options
            )
        finally:
            r.build_provider = original

    def test_gate_pass_and_fail_with_exit_status(
        self, settings: Any, capsys: Any
    ) -> None:
        settings.EVAL_GATE_MIN_CASES = 1
        settings.EVAL_GATE_MAX_DROP_POINTS = 0.0
        case(1, "approved", "Count the orders")
        self.run("SELECT count(*) AS n FROM orders")
        self.run("SELECT count(*) AS n FROM orders", gate=True)
        assert "GATE PASSED" in capsys.readouterr().out
        with pytest.raises(CommandError, match="Gate failed"):
            self.run("SELECT 123456 AS n FROM orders", gate=True)
        out = capsys.readouterr().out
        assert "GATE FAILED" in out and "to_wrong" in out

    def test_a_gate_without_any_baseline_fails(self) -> None:
        case(1, "approved", "Count the orders")
        with pytest.raises(CommandError, match="no earlier finished run"):
            self.run("SELECT count(*) AS n FROM orders", gate=True)

    def test_an_explicit_baseline_and_misuse(self, settings: Any) -> None:
        settings.EVAL_GATE_MIN_CASES = 1
        case(1, "approved", "Count the orders")
        self.run("SELECT count(*) AS n FROM orders")
        base = EvalRun.objects.get()
        self.run("SELECT count(*) AS n FROM orders", gate=True, baseline=base.pk)
        with pytest.raises(CommandError, match="needs --gate"):
            self.run("SELECT 1 FROM orders", baseline=base.pk)
        with pytest.raises(CommandError, match="No such baseline"):
            self.run("SELECT 1 FROM orders", gate=True, baseline=9999)
