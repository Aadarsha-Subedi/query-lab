"""The Olist golden set: file hygiene, and every gold query runs on the demo data."""

import json
from pathlib import Path

import pytest

from ask import guard, schema
from evals.targets import olist


def test_ids_are_unique_and_fields_present() -> None:
    items = olist.read_golden()
    assert 36 <= len(items) <= 60
    assert len({item["id"] for item in items}) == len(items)
    for item in items:
        assert set(item) == {
            "id",
            "question",
            "gold_sql",
            "tags",
            "answerable",
            "reviewed",
        }
        assert item["question"].strip()
        assert bool(item["gold_sql"]) == item["answerable"]


def test_some_questions_are_unanswerable() -> None:
    assert sum(not i["answerable"] for i in olist.read_golden()) >= 4


def test_unreviewed_questions_are_skipped_unless_asked() -> None:
    everything = olist.OlistTarget(include_unreviewed=True).questions("all")
    reviewed = olist.OlistTarget().questions("all")
    assert len(everything) == len(olist.read_golden())
    assert len(reviewed) == sum(i["reviewed"] for i in olist.read_golden())


def test_no_splits() -> None:
    with pytest.raises(ValueError):
        olist.OlistTarget().questions("held-out")


def test_mark_reviewed_rewrites_the_file(tmp_path: Path, monkeypatch) -> None:
    copy = tmp_path / "golden.jsonl"
    copy.write_text(olist.GOLDEN_FILE.read_text())
    monkeypatch.setattr(olist, "GOLDEN_FILE", copy)
    count = olist.mark_reviewed(copy)
    assert count == len(copy.read_text().splitlines())
    assert all(json.loads(line)["reviewed"] for line in copy.read_text().splitlines())


@pytest.mark.django_db
@pytest.mark.usefixtures("data_connections")
def test_every_gold_query_passes_the_guard_and_runs() -> None:
    target = olist.OlistTarget(include_unreviewed=True)
    known = schema.get_schema(include_samples=True)
    for question in target.questions("all"):
        if not question.answerable:
            continue
        checked = guard.check(question.gold_sql, known)
        result = target.execute(question)(checked.sql)
        assert result.row_count > 0, question.id
        assert not result.truncated, question.id
