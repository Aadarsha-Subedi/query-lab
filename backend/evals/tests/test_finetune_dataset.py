import json
import shutil
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from ask import prompt
from evals.targets import spider
from finetune import dataset

SPLIT = {
    "tune": ["shop"],
    "held-out": ["zoo"],
}


def items(*rows: tuple[str, str, str]) -> list[dict]:
    return [{"db_id": d, "question": q, "query": s} for d, q, s in rows]


def test_record_round_trips_through_parse_reply() -> None:
    [example] = dataset.examples_from_spider(
        items(("shop", "How many items?", "SELECT count(*) FROM item;")),
        source="spider-train",
    )
    record = dataset.to_record(example, "table item(id)")
    system, user, assistant = record["messages"]  # type: ignore[misc]
    assert system["content"] == prompt.system_prompt(prompt.DIALECT_SQLITE)
    assert user["content"] == prompt.build_prompt("How many items?", "table item(id)")
    parsed = prompt.parse_reply(assistant["content"])
    assert parsed.answerable
    assert parsed.sql == "SELECT count(*) FROM item"


def test_dedupe_keeps_first_per_database_and_question() -> None:
    examples = dataset.examples_from_spider(
        items(
            ("a", "How  many?", "SELECT 1"),
            ("a", "how many?", "SELECT 2"),
            ("b", "how many?", "SELECT 3"),
        ),
        source="spider-train",
    )
    assert [e.sql for e in dataset.dedupe(examples)] == ["SELECT 1", "SELECT 3"]


def test_leakage_by_database_and_by_question() -> None:
    examples = dataset.examples_from_spider(
        items(("zoo", "List animals", "SELECT 1")), source="spider-train"
    )
    with pytest.raises(dataset.LeakageError):
        dataset.assert_no_leakage(examples, banned_dbs={"zoo"}, banned_questions=[])
    with pytest.raises(dataset.LeakageError):
        dataset.assert_no_leakage(
            examples, banned_dbs=set(), banned_questions=["  list ANIMALS "]
        )
    dataset.assert_no_leakage(examples, banned_dbs={"x"}, banned_questions=["y"])


def test_validation_is_whole_databases_and_deterministic() -> None:
    examples = dataset.examples_from_spider(
        items(*[(f"db{i % 5}", f"q{i}", "SELECT 1") for i in range(20)]),
        source="spider-train",
    )
    train, validation = dataset.split_by_database(examples, 0.2, seed=1)
    assert {e.db_id for e in train}.isdisjoint({e.db_id for e in validation})
    assert len({e.db_id for e in validation}) == 1
    assert len(train) + len(validation) == 20
    assert dataset.split_by_database(examples, 0.2, seed=1) == (train, validation)


@pytest.fixture
def finetune_env(spider_dir: Path, tmp_path: Path, monkeypatch):
    split_file = tmp_path / "split.json"
    split_file.write_text(json.dumps(SPLIT))
    monkeypatch.setattr(spider, "SPLIT_FILE", split_file)
    out = tmp_path / "out"
    with override_settings(
        FINETUNE_OUTPUT_DIR=str(out),
        FINETUNE_SEED=3,
        FINETUNE_VALIDATION_FRACTION=0.5,
        FINETUNE_MAX_EXAMPLES=0,
        FINETUNE_BASE_MODEL="base",
    ):
        yield spider_dir, out


def write_train(spider_dir: Path, rows: list[dict]) -> None:
    (spider_dir / "train_spider.json").write_text(json.dumps(rows))


def test_command_writes_files_without_benchmark_data(finetune_env) -> None:
    spider_dir, out = finetune_env
    # Two train databases are needed to hold one out for validation.
    (spider_dir / "train_spider.json").write_text(
        json.dumps(
            items(
                ("shop", "Count the sales", "SELECT count(*) FROM sale"),
                ("shop2", "Names of items", "SELECT name FROM item"),
            )
        )
    )
    shutil.copytree(spider_dir / "database/shop", spider_dir / "database/shop2")
    (spider_dir / "database/shop2/shop.sqlite").rename(
        spider_dir / "database/shop2/shop2.sqlite"
    )
    call_command("build_finetune_data")
    train = [json.loads(x) for x in (out / "train.jsonl").read_text().splitlines()]
    validation = [
        json.loads(x) for x in (out / "validation.jsonl").read_text().splitlines()
    ]
    manifest = json.loads((out / "manifest.json").read_text())
    everything = train + validation
    assert {r["db_id"] for r in everything} >= {"shop2"}
    assert all(r["db_id"] != "zoo" for r in everything)
    assert all("List animals" not in r["messages"][1]["content"] for r in everything)
    assert manifest["train_examples"] == len(train)
    assert set(manifest["sha256"]) == {"train.jsonl", "validation.jsonl"}
    first = (out / "train.jsonl").read_text()
    call_command("build_finetune_data")
    assert (out / "train.jsonl").read_text() == first


def test_command_refuses_a_held_out_database(finetune_env) -> None:
    spider_dir, _ = finetune_env
    write_train(spider_dir, items(("zoo", "Other question", "SELECT 1")))
    with pytest.raises(CommandError, match="held out"):
        call_command("build_finetune_data")


def test_command_needs_the_train_file(finetune_env) -> None:
    with pytest.raises(CommandError, match=r"train_spider\.json"):
        call_command("build_finetune_data")
