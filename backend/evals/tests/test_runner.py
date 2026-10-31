"""The harness end to end with scripted LLMs: Olist on the real demo data and
Spider on the fixture database."""

from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from common.llm import LLMRateLimitedError
from evals import runner
from evals.models import EvalResult, EvalRun
from evals.targets import olist, spider
from evals.tests.conftest import ScriptedProvider, reply

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]


def olist_target() -> olist.OlistTarget:
    return olist.OlistTarget(include_unreviewed=True)


def gold_by_question() -> dict[str, dict]:
    return {item["question"]: item for item in olist.read_golden()}


def gold_answers(question: str) -> str:
    item = gold_by_question()[question]
    if not item["answerable"]:
        return reply("", answerable=False)
    return reply(item["gold_sql"])


def run_olist(provider: ScriptedProvider, **kwargs) -> EvalRun:
    target = olist_target()
    return runner.run_eval(
        target,
        split="all",
        provider_name="gemini",
        provider=provider,
        questions=target.questions("all"),
        sleep=lambda seconds: None,
        **kwargs,
    )


def outcomes(run: EvalRun) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in run.results.all():
        counts[result.outcome] = counts.get(result.outcome, 0) + 1
    return counts


def test_olist_gold_answers_are_all_correct() -> None:
    run = run_olist(ScriptedProvider(gold_answers))
    assert run.status == EvalRun.STATUS_DONE
    assert run.question_count == len(olist.read_golden())
    assert run.correct_count == run.question_count
    assert outcomes(run) == {"correct": run.question_count}
    assert run.prompt_version
    assert run.finished_at


def test_wrong_sql_is_wrong_and_unanswerable_still_declined() -> None:
    def answer(question: str) -> str:
        if not gold_by_question()[question]["answerable"]:
            return reply("", answerable=False)
        return reply("SELECT 1 AS n, 2 AS m")

    run = run_olist(ScriptedProvider(answer))
    counts = outcomes(run)
    unanswerable = sum(not i["answerable"] for i in olist.read_golden())
    assert counts["correct"] == unanswerable  # only the correct declines
    assert counts["wrong"] == run.question_count - unanswerable


def test_hostile_sql_is_guard_rejected_and_never_runs() -> None:
    run = run_olist(ScriptedProvider(lambda q: reply("DROP TABLE demo.orders")))
    assert {r.outcome for r in run.results.filter(gold_sql__gt="")} == {
        "guard_rejected"
    }
    assert run.correct_count == 0  # nothing was declined, so nothing is right


def test_declining_an_answerable_question_is_a_miss_not_an_error() -> None:
    run = run_olist(ScriptedProvider(lambda q: reply("", answerable=False)))
    counts = outcomes(run)
    assert counts["not_answerable"] == sum(i["answerable"] for i in olist.read_golden())
    assert counts["correct"] == sum(not i["answerable"] for i in olist.read_golden())


def test_answering_an_unanswerable_question_is_wrong() -> None:
    run = run_olist(ScriptedProvider(lambda q: reply("SELECT 1")))
    unanswerable = run.results.filter(gold_sql="")
    assert {r.reason for r in unanswerable} == {"answered_unanswerable"}
    assert {r.outcome for r in unanswerable} == {"wrong"}


def test_results_hold_sql_but_never_rows() -> None:
    run = run_olist(ScriptedProvider(gold_answers))
    first = run.results.first()
    assert first is not None
    assert first.predicted_sql.startswith("SELECT")
    assert first.confidence is not None and first.input_tokens == 10


def test_gold_sql_never_reaches_the_prompt() -> None:
    provider = ScriptedProvider(gold_answers)
    run_olist(provider)
    sent = "\n".join(provider.prompts)
    for item in olist.read_golden():
        if item["gold_sql"]:
            assert item["gold_sql"] not in sent


def test_provider_rate_limit_is_retried_then_succeeds() -> None:
    state = {"failed": False}
    slept: list[float] = []

    class Flaky(ScriptedProvider):
        def generate(self, request):
            if not state["failed"]:
                state["failed"] = True
                raise LLMRateLimitedError()
            return super().generate(request)

    target = olist_target()
    question = target.questions("all")[0]
    outcome = runner.ask_once(target, question, Flaky(gold_answers), sleep=slept.append)
    assert outcome.outcome == EvalResult.OUTCOME_CORRECT
    assert slept == [runner.BACKOFF_BASE_SECONDS]


@override_settings(EVAL_LLM_RETRIES=1)
def test_rate_limit_that_never_clears_is_llm_failed() -> None:
    class Always(ScriptedProvider):
        def generate(self, request):
            raise LLMRateLimitedError()

    target = olist_target()
    outcome = runner.ask_once(
        target, target.questions("all")[0], Always(gold_answers), sleep=lambda s: None
    )
    assert outcome.outcome == EvalResult.OUTCOME_LLM_FAILED
    assert outcome.reason == "llm_rate_limited"


def test_interrupted_run_resumes_without_repeating_questions() -> None:
    class Dies(ScriptedProvider):
        def generate(self, request):
            if self.calls >= 3:
                raise KeyboardInterrupt
            return super().generate(request)

    target = olist_target()
    questions = target.questions("all")
    with pytest.raises(KeyboardInterrupt):
        runner.run_eval(
            target,
            split="all",
            provider_name="gemini",
            provider=Dies(gold_answers),
            questions=questions,
        )
    run = EvalRun.objects.get()
    assert run.status == EvalRun.STATUS_FAILED
    assert run.results.count() == 3

    provider = ScriptedProvider(gold_answers)
    done = runner.run_eval(
        target,
        split="all",
        provider_name="gemini",
        provider=provider,
        questions=questions,
        run=run,
    )
    assert done.status == EvalRun.STATUS_DONE
    assert done.results.count() == len(questions)
    assert provider.calls == len(questions) - 3


def test_pick_questions_is_a_stable_sample() -> None:
    questions = olist_target().questions("all")
    first = runner.pick_questions(questions, limit=5, seed=1)
    assert first == runner.pick_questions(questions, limit=5, seed=1)
    assert len(first) == 5
    assert first != runner.pick_questions(questions, limit=5, seed=2)
    assert runner.pick_questions(questions, limit=None, seed=1) == questions


def test_unknown_model_is_refused() -> None:
    with pytest.raises(runner.EvalConfigError):
        runner.build_provider("gpt-nonexistent")


def test_known_models_get_the_right_provider() -> None:
    assert runner.build_provider("gemini-3.5-flash")[0] == "gemini"
    assert runner.build_provider("gpt-5-mini")[0] == "openai"


def test_spider_run_on_the_fixture(spider_dir: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        spider, "load_split", lambda: {"shop": "tune", "zoo": "held-out"}
    )
    target = spider.SpiderTarget()
    by_question = {q.question: q for q in target.questions("all")}
    provider = ScriptedProvider(lambda q: reply(by_question[q].gold_sql))
    run = runner.run_eval(
        target,
        split="all",
        provider_name="gemini",
        provider=provider,
        questions=target.questions("all"),
    )
    assert (run.question_count, run.correct_count) == (2, 2)
    assert "SQLite" in provider.prompts[0]
    assert "CREATE TABLE item" in provider.prompts[0]


def test_run_eval_command_runs_and_prints(
    spider_dir: Path, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        spider, "load_split", lambda: {"shop": "tune", "zoo": "held-out"}
    )
    provider = ScriptedProvider(
        lambda q: reply(
            "SELECT count(*) FROM item" if "items" in q else "SELECT name FROM animal"
        )
    )
    monkeypatch.setattr(runner, "build_provider", lambda model: ("gemini", provider))
    call_command("run_eval", target="spider", model="m", split="all", yes=True)
    out = capsys.readouterr().out
    assert "Execution accuracy: 100.0% (2/2)" in out
    assert "Confidence vs accuracy" in out
    assert EvalRun.objects.count() == 1


@override_settings(EVAL_CONFIRM_ABOVE_CALLS=1)
def test_cost_guard_needs_yes(spider_dir: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        spider, "load_split", lambda: {"shop": "tune", "zoo": "held-out"}
    )
    provider = ScriptedProvider(lambda q: reply("SELECT 1"))
    monkeypatch.setattr(runner, "build_provider", lambda model: ("gemini", provider))
    with pytest.raises(CommandError, match="--yes"):
        call_command("run_eval", target="spider", model="m", split="all")
    assert provider.calls == 0


def test_command_refuses_unreviewed_olist_questions() -> None:
    with pytest.raises(CommandError, match="review"):
        call_command("run_eval", target="olist", model="gemini-3.5-flash", yes=True)
