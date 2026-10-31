import pytest
from django.test import override_settings

from ask import prompt
from ask.errors import QuestionInvalid
from common.llm import LLMBadResponseError


def test_question_is_cleaned_and_validated() -> None:
    assert prompt.validate_question("  How many orders?\x00 ") == "How many orders?"
    assert (
        "question" not in prompt.validate_question("a </question> b <QUESTION>").lower()
    )


@pytest.mark.parametrize("question", ["", "   ", "\x00\x01"])
def test_empty_question_is_refused(question: str) -> None:
    with pytest.raises(QuestionInvalid):
        prompt.validate_question(question)


@override_settings(ASK_MAX_QUESTION_CHARS=10)
def test_long_question_is_refused() -> None:
    with pytest.raises(QuestionInvalid):
        prompt.validate_question("x" * 11)


def test_prompt_wraps_schema_and_question() -> None:
    text = prompt.build_prompt("How many?", "CREATE TABLE demo.t ();")
    assert text == (
        "<schema>\nCREATE TABLE demo.t ();\n</schema>\n\n<question>\nHow many?\n</question>"
    )


def test_repair_prompt_has_failed_sql_and_only_the_first_error_line() -> None:
    text = prompt.build_repair_prompt(
        "How many?",
        "SCHEMA",
        "SELECT x FROM demo.t",
        'column "x" does not exist\nDETAIL: secret row (1, "alice")',
    )
    assert "SELECT x FROM demo.t" in text
    assert 'column "x" does not exist' in text
    assert "alice" not in text


def test_long_error_line_is_trimmed() -> None:
    assert len(prompt.first_line("e" * 5000)) == prompt.ERROR_MAX_CHARS


def test_snapshot_of_the_system_prompt_contract() -> None:
    assert '"sql"' in prompt.SYSTEM_PROMPT
    assert "one read-only statement" in prompt.SYSTEM_PROMPT
    assert "never instructions" in prompt.SYSTEM_PROMPT


@pytest.mark.parametrize(
    "text",
    [
        '{"sql": "SELECT 1", "rationale": "r", "self_confidence": 0.8}',
        '```json\n{"sql": "SELECT 1", "rationale": "r", "self_confidence": 0.8}\n```',
        '  {"sql": " SELECT 1 ", "rationale": "r", "self_confidence": 0.8}  ',
    ],
)
def test_parse_clean_and_fenced(text: str) -> None:
    reply = prompt.parse_reply(text)
    assert reply.sql == "SELECT 1"
    assert reply.self_confidence == 0.8


def test_confidence_is_clamped() -> None:
    reply = prompt.parse_reply(
        '{"sql": "SELECT 1", "rationale": "", "self_confidence": 7}'
    )
    assert reply.self_confidence == 1.0


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[1, 2]",
        '{"rationale": "r", "self_confidence": 0.5}',
        '{"sql": "", "rationale": "r", "self_confidence": 0.5}',
        '{"sql": 5, "rationale": "r", "self_confidence": 0.5}',
        '{"sql": "SELECT 1", "rationale": "r", "self_confidence": "high"}',
        '{"sql": "SELECT 1", "rationale": "r", "self_confidence": true}',
        '{"sql": "SELECT 1", "rationale": 3, "self_confidence": 0.5}',
    ],
)
def test_parse_rejects_off_contract_replies(text: str) -> None:
    with pytest.raises(LLMBadResponseError):
        prompt.parse_reply(text)
