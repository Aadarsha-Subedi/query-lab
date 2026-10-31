"""The agent runner end to end on the real demo data, with a scripted model."""

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from agent.models import AgentRun
from common.llm import LLMRequest, LLMResponse
from common.llm.base import LLMProvider
from evals import confidence_analysis, runner, scoring
from evals.models import EvalResult, EvalRun
from evals.targets import olist
from evals.tests.conftest import QUESTION

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]


def gold_by_question() -> dict[str, dict]:
    return {item["question"]: item for item in olist.read_golden()}


class AgentScript(LLMProvider):
    """Plays the model for the agent: plan, then one propose_sql (or give_up),
    then `ok` to any review. `sql_for(item)` picks the SQL it proposes."""

    provider = "gemini"

    def __init__(self, sql_for=None, model: str = "scripted") -> None:
        self.model = model
        self.sql_for = sql_for or (lambda item: item["gold_sql"])
        self.calls = 0

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        if (
            "Reply with one JSON object" in request.system
            and '"verdict"' in request.system
        ):
            text = json.dumps({"verdict": "ok", "reason": "fine"})
        else:
            match = QUESTION.search(request.prompt)
            assert match
            item = gold_by_question()[match.group(1)]
            if '"plan"' in request.system:
                text = json.dumps({"plan": ["propose"], "assumptions": []})
            elif not item["answerable"]:
                text = json.dumps({"tool": "give_up", "input": {"reason": "no data"}})
            else:
                text = json.dumps(
                    {
                        "tool": "propose_sql",
                        "input": {"sql": self.sql_for(item), "rationale": "r"},
                    }
                )
        return LLMResponse(text, self.model, 10, 5)

    def validate_key(self) -> None:
        return None


def run_agent(provider: LLMProvider, *, small: bool = True) -> EvalRun:
    """`small` runs 5 answerable questions and 1 unanswerable one; the full golden
    set runs once, in the first test."""
    target = olist.OlistTarget(include_unreviewed=True)
    questions = target.questions("all")
    if small:
        questions = [q for q in questions if q.answerable][:5] + [
            q for q in questions if not q.answerable
        ][:1]
    return runner.run_eval(
        target,
        split="all",
        provider_name="gemini",
        provider=provider,
        questions=questions,
        runner_name=EvalRun.RUNNER_AGENT,
        sleep=lambda seconds: None,
    )


def test_gold_answers_through_the_agent_are_all_correct_and_traced() -> None:
    run = run_agent(AgentScript(), small=False)
    assert run.runner == EvalRun.RUNNER_AGENT
    assert run.prompt_version == "v2-agent"
    assert run.correct_count == run.question_count == len(olist.read_golden())
    assert run.results.count() == run.question_count

    answered = run.results.exclude(agent_run=None).filter(predicted_sql__gt="").first()
    assert answered is not None and answered.agent_run is not None
    assert answered.steps == answered.agent_run.step_count >= 5
    assert answered.llm_calls == answered.agent_run.llm_calls >= 2
    execute = answered.agent_run.steps.get(kind="execute")
    assert (execute.actor, execute.input["edited"]) == ("eval", False)
    assert answered.agent_run.steps.filter(kind="approval", actor="eval").exists()
    assert answered.agent_run.key_source == "eval"


def test_report_shows_what_the_agent_cost() -> None:
    run = run_agent(AgentScript())
    summary = scoring.summarise(run)
    assert summary.mean_steps > 4 and summary.mean_llm_calls >= 2
    report = scoring.format_report(run)
    assert "agent runner" in report
    assert "Agent cost per question" in report


def test_wrong_sql_is_wrong_and_unanswerable_is_declined() -> None:
    run = run_agent(AgentScript(sql_for=lambda item: "SELECT 1 AS n, 2 AS m"))
    assert run.correct_count == 1  # only the declined unanswerable question
    assert {r.outcome for r in run.results.filter(gold_sql__gt="")} == {"wrong"}


def test_a_proposal_the_guard_refuses_never_runs() -> None:
    run = run_agent(AgentScript(sql_for=lambda item: "DROP TABLE demo.orders"))
    answerable = run.results.filter(gold_sql__gt="")
    assert {r.outcome for r in answerable} == {"error"}
    assert {r.reason for r in answerable} == {"agent_llm_calls_exceeded"}
    assert not AgentRun.objects.filter(steps__kind="execute").exists()


def test_confidence_analysis_reads_the_trace() -> None:
    run = run_agent(AgentScript())
    analysis = confidence_analysis.analyse(run)
    assert analysis.answered == run.results.filter(gold_sql__gt="").count()
    assert analysis.right == analysis.answered
    names = [row.name for row in analysis.rows]
    assert names == list(confidence_analysis.FEATURES)
    text = confidence_analysis.format_analysis(run, analysis)
    assert "CONFIDENCE_MIN_SEPARATION" in text
    assert ("PASS" in text) == analysis.passes or "FAIL" in text


def test_command_options(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(CommandError, match="Olist only"):
        call_command(
            "run_eval", target="spider", model="gemini-3.5-flash", runner="agent"
        )
    ask_run = EvalRun.objects.create(
        target="olist", split="all", provider="gemini", model="m", prompt_version="v1"
    )
    EvalResult.objects.create(
        run=ask_run, question_id="q", question="q", outcome="correct"
    )
    with pytest.raises(CommandError, match="agent runner"):
        call_command("confidence_report", run=ask_run.pk)
