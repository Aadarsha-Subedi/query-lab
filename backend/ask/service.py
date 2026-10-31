"""The ask path: question in, checked SQL and a result table out.

schema -> prompt -> LLM -> parse -> guard -> run, with up to
ASK_MAX_REPAIR_ATTEMPTS repair retries when the guard refuses the SQL or
Postgres rejects it. Every ask writes one AskLog row."""

import logging
import time
from dataclasses import dataclass, field

from django.conf import settings

from accounts.models import User
from ask import confidence, guard, keys, prompt, runner, schema
from ask.errors import (
    GuardRejected,
    LLMFailed,
    NotAnswerable,
    QueryFailed,
    QueryTimeout,
)
from ask.models import AskLog
from common.exception.domain import AppException
from common.llm import LLMError, LLMRequest

logger = logging.getLogger(__name__)

NOT_ANSWERABLE_MAX_CHARS = 300

STATUS_BY_ERROR_CODE = {
    GuardRejected.error_code: AskLog.STATUS_GUARD_REJECTED,
    QueryFailed.error_code: AskLog.STATUS_QUERY_FAILED,
    QueryTimeout.error_code: AskLog.STATUS_TIMEOUT,
    NotAnswerable.error_code: AskLog.STATUS_NOT_ANSWERABLE,
}


@dataclass(frozen=True)
class AskResult:
    question: str
    sql: str
    columns: list[str]
    rows: list[list]
    row_count: int
    truncated: bool
    confidence: float
    rationale: str
    model: str
    latency_ms: int


@dataclass
class Trace:
    """What happened during one ask; becomes the AskLog row."""

    question: str
    started: float = field(default_factory=time.perf_counter)
    sql: str = ""
    attempts: int = 0
    provider: str = ""
    model: str = ""
    key_source: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    confidence: float | None = None
    row_count: int = 0

    @property
    def latency_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)


def _write_log(user: User, trace: Trace, status: str, error_code: str = "") -> None:
    try:
        AskLog.objects.create(
            user=user,
            question=trace.question,
            sql=trace.sql,
            status=status,
            error_code=error_code,
            attempts=trace.attempts,
            provider=trace.provider,
            model=trace.model,
            key_source=trace.key_source,
            input_tokens=trace.input_tokens,
            output_tokens=trace.output_tokens,
            latency_ms=trace.latency_ms,
            confidence=trace.confidence,
            row_count=trace.row_count,
        )
    except Exception:  # a failed log must never break the answer
        logger.exception("Could not write the ask log")


def _failure_status(error: AppException) -> str:
    if error.error_code.startswith("llm_") or isinstance(error, LLMFailed):
        return AskLog.STATUS_LLM_FAILED
    return STATUS_BY_ERROR_CODE.get(error.error_code, AskLog.STATUS_REFUSED)


def answer(user: User, question: str) -> AskResult:
    """Answer one question, or raise a typed AppException."""
    trace = Trace(question=question)
    try:
        result = _answer(user, question, trace)
    except AppException as error:
        _write_log(user, trace, _failure_status(error), error.error_code)
        raise
    _write_log(user, trace, AskLog.STATUS_OK)
    return result


def _answer(user: User, question: str, trace: Trace) -> AskResult:
    question = prompt.validate_question(question)
    trace.question = question

    resolved = keys.resolve_provider(user)
    trace.provider = resolved.provider_name
    trace.model = resolved.provider.model
    trace.key_source = resolved.key_source
    if resolved.key_source == keys.KEY_DEFAULT:
        keys.spend_default_key(user)

    known = schema.get_schema(include_samples=True)
    schema_text = schema.render(known)

    text = prompt.build_prompt(question, schema_text)
    max_attempts = 1 + settings.ASK_MAX_REPAIR_ATTEMPTS
    for attempt in range(1, max_attempts + 1):
        trace.attempts = attempt
        try:
            reply = resolved.provider.generate(
                LLMRequest(prompt=text, system=prompt.SYSTEM_PROMPT, json_output=True)
            )
            trace.input_tokens += reply.input_tokens
            trace.output_tokens += reply.output_tokens
            parsed = prompt.parse_reply(reply.text)
        except LLMError as error:
            raise LLMFailed(error.message, error_code=error.code) from None
        if not parsed.answerable:
            raise NotAnswerable(parsed.rationale[:NOT_ANSWERABLE_MAX_CHARS] or None)
        trace.sql = parsed.sql
        try:
            checked = guard.check(parsed.sql, known)
            trace.sql = checked.sql
            result = runner.run(checked.sql)
        except (GuardRejected, QueryFailed) as error:
            if attempt == max_attempts:
                raise
            text = prompt.build_repair_prompt(
                question, schema_text, trace.sql, error.detail
            )
            continue
        break

    trace.confidence = confidence.score(
        self_confidence=parsed.self_confidence,
        guard=checked.report,
        attempts=trace.attempts,
        row_count=result.row_count,
        truncated=result.truncated,
    )
    trace.row_count = result.row_count
    return AskResult(
        question=question,
        sql=checked.sql,
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        truncated=result.truncated,
        confidence=trace.confidence,
        rationale=parsed.rationale,
        model=resolved.provider.model,
        latency_ms=trace.latency_ms,
    )
