"""Shared fixtures: a tiny Spider on disk, and fake LLMs that answer from gold SQL."""

import json
import re
import sqlite3
from pathlib import Path

import pytest
from django.test import override_settings

from common.llm import LLMRequest, LLMResponse
from common.llm.base import LLMProvider

DEV = [
    {
        "db_id": "shop",
        "question": "How many items?",
        "query": "SELECT count(*) FROM item",
    },
    {"db_id": "zoo", "question": "List animals", "query": "SELECT name FROM animal"},
]


@pytest.fixture
def spider_dir(tmp_path: Path):
    for db_id, ddl in {
        "shop": [
            "CREATE TABLE item (id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT)",
            "CREATE TABLE sale (id INTEGER PRIMARY KEY, item_id INTEGER, "
            "FOREIGN KEY (item_id) REFERENCES item(id))",
            "INSERT INTO item (name, kind) VALUES ('a', 'x'), ('b', 'x'), ('c', 'y')",
        ],
        "zoo": [
            "CREATE TABLE animal (name TEXT)",
            "INSERT INTO animal VALUES ('lion')",
        ],
    }.items():
        folder = tmp_path / "database" / db_id
        folder.mkdir(parents=True)
        connection = sqlite3.connect(folder / f"{db_id}.sqlite")
        for statement in ddl:
            connection.execute(statement)
        connection.commit()
        connection.close()
    (tmp_path / "dev.json").write_text(json.dumps(DEV))
    with override_settings(EVAL_SPIDER_DIR=tmp_path):
        yield tmp_path


QUESTION = re.compile(r"<question>\n(.*?)\n</question>", re.DOTALL)


def reply(sql: str, confidence: float = 0.9, answerable: bool = True) -> str:
    return json.dumps(
        {
            "answerable": answerable,
            "sql": sql,
            "rationale": "r",
            "self_confidence": confidence,
        }
    )


class ScriptedProvider(LLMProvider):
    """Answers each question with `answer(question_text)`; counts the calls."""

    provider = "gemini"

    def __init__(self, answer, model: str = "scripted") -> None:
        self.model = model
        self.answer = answer
        self.calls = 0
        self.prompts: list[str] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        self.prompts.append(request.prompt + request.system)
        match = QUESTION.search(request.prompt)
        assert match
        return LLMResponse(self.answer(match.group(1)), self.model, 10, 5)

    def validate_key(self) -> None:
        return None
