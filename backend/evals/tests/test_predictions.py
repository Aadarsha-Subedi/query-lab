"""Scoring answers from a file (step 7), on the tiny Spider fixture."""

import json
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from ask import prompt
from evals import predictions
from evals.models import EvalResult, EvalRun
from evals.targets import spider
from evals.tests.conftest import reply

pytestmark = pytest.mark.django_db


@pytest.fixture
def split(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "split.json"
    path.write_text(json.dumps({"tune": ["zoo"], "held-out": ["shop"]}))
    monkeypatch.setattr(spider, "SPLIT_FILE", path)


def held_out_prompts() -> dict[str, str]:
    target = spider.SpiderTarget()
    return {
        q.id: predictions.user_prompt(q.question, target.schema_text(q))
        for q in target.questions("held-out")
    }


def write_file(path: Path, sql_by_id: dict[str, str], label: str = "tuned") -> Path:
    prompts = held_out_prompts()
    lines: list[dict] = [{"header": {"label": label, "adapter_sha256": "abc"}}]
    for question_id, sql in sql_by_id.items():
        lines.append(
            {
                "prompt_sha256": predictions.prompt_hash(prompts[question_id]),
                "raw_reply": reply(sql),
                "input_tokens": 7,
                "output_tokens": 3,
            }
        )
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    return path


def run(path: Path, *extra: str) -> StringIO:
    out = StringIO()
    call_command(
        "run_eval",
        "--target=spider",
        "--split=held-out",
        f"--predictions={path}",
        *extra,
        stdout=out,
    )
    return out


def test_file_answers_are_scored_with_the_normal_comparison(
    spider_dir: Path, split: None, tmp_path: Path
) -> None:
    file = write_file(tmp_path / "p.jsonl", {"dev-0000": "SELECT count(*) FROM item"})
    run(file)
    eval_run = EvalRun.objects.get()
    assert (eval_run.provider, eval_run.model) == ("file", "tuned")
    assert eval_run.correct_count == eval_run.question_count == 1
    result = eval_run.results.get()
    assert result.outcome == EvalResult.OUTCOME_CORRECT
    assert (result.input_tokens, result.output_tokens) == (7, 3)


def test_wrong_sql_is_wrong_and_a_failing_one_is_not_repaired(
    spider_dir: Path, split: None, tmp_path: Path
) -> None:
    wrong = write_file(tmp_path / "w.jsonl", {"dev-0000": "SELECT 1"})
    run(wrong)
    assert EvalRun.objects.get().results.get().outcome == EvalResult.OUTCOME_WRONG
    EvalRun.objects.all().delete()
    broken = write_file(tmp_path / "b.jsonl", {"dev-0000": "SELECT nope FROM item"})
    run(broken)
    result = EvalRun.objects.get().results.get()
    assert result.outcome == EvalResult.OUTCOME_ERROR
    assert (
        result.attempts == 1 + settings.ASK_MAX_REPAIR_ATTEMPTS
    )  # the same reply replayed, never a new answer


def test_a_missing_answer_stops_before_any_scoring(
    spider_dir: Path, split: None, tmp_path: Path
) -> None:
    file = write_file(tmp_path / "p.jsonl", {})
    file.write_text(
        '{"header": {"label": "x"}}\n{"prompt_sha256": "nope", "raw_reply": "{}"}\n'
    )
    with pytest.raises(CommandError, match="no answer in the file"):
        run(file)
    assert not EvalRun.objects.exists()


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not json\n",
        '{"header": {}}\n',
        '{"header": {"label": "x"}}\n',
        '{"header": {"label": "x"}}\n{"prompt_sha256": "a"}\n',
        '{"header": {"label": "x"}}\n'
        '{"prompt_sha256": "a", "raw_reply": "r"}\n'
        '{"prompt_sha256": "a", "raw_reply": "r"}\n',
    ],
)
def test_bad_files_are_refused(tmp_path: Path, text: str) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(text)
    with pytest.raises(predictions.PredictionsError):
        predictions.load(path)


def test_the_file_needs_no_provider_key(
    spider_dir: Path, split: None, tmp_path: Path, settings
) -> None:
    settings.LLM_DEFAULT_API_KEY = ""
    file = write_file(tmp_path / "p.jsonl", {"dev-0000": "SELECT count(*) FROM item"})
    run(file)
    assert EvalRun.objects.count() == 1


def test_model_or_predictions_is_required(spider_dir: Path, split: None) -> None:
    with pytest.raises(CommandError, match="--model or --predictions"):
        call_command("run_eval", "--target=spider")


@pytest.mark.usefixtures("data_connections")
def test_export_holds_prompts_but_no_gold(
    spider_dir: Path, split: None, tmp_path: Path
) -> None:
    out = tmp_path / "bench.jsonl"
    call_command("export_benchmark", f"--out={out}")
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert {r["target"] for r in rows} == {"spider", "olist"}
    assert any(r["id"] == "spider:dev-0000" for r in rows)
    text = out.read_text()
    assert "SELECT count(*) FROM item" not in text  # Spider gold SQL
    assert "gold_sql" not in text
    for row in rows:
        assert row["prompt_sha256"] == predictions.prompt_hash(row["prompt"])


def test_prompt_matches_what_the_model_is_shown(spider_dir: Path, split: None) -> None:
    target = spider.SpiderTarget()
    [question] = target.questions("held-out")
    shown = prompt.build_prompt(question.question, target.schema_text(question))
    assert (
        predictions.user_prompt(question.question, target.schema_text(question))
        == shown
    )
