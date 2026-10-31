"""The ask path: question in, checked SQL and a result table out.

schema -> prompt -> LLM -> parse -> guard -> run, with up to
ASK_MAX_REPAIR_ATTEMPTS repair retries when the guard refuses the SQL or
Postgres rejects it. Every ask writes one AskLog row."""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from django.conf import settings

from accounts.models import User
from agent import confidence
from ask import guard, keys, prompt, runner, schema
from ask.errors import (
    GuardRejected,
    LLMFailed,
    NotAnswerable,
    QueryFailed,
    QueryTimeout,
)
from ask.models import AskLog
from common.exception.domain import AppException
from common.llm import LLMError, LLMProvider, LLMRequest
from core.datadb import DEMO_SCHEMA
from workspaces.context import DEMO, WorkspaceRef

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
    check: str
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


def answer(user: User, question: str, workspace: WorkspaceRef = DEMO) -> AskResult:
    """Answer one question, or raise a typed AppException."""
    trace = Trace(question=question)
    try:
        result = _answer(user, question, trace, workspace)
    except AppException as error:
        _write_log(user, trace, _failure_status(error), error.error_code)
        raise
    _write_log(user, trace, AskLog.STATUS_OK)
    return result


def _answer(
    user: User, question: str, trace: Trace, workspace: WorkspaceRef
) -> AskResult:
    question = prompt.validate_question(question)
    trace.question = question

    resolved = keys.resolve_provider(user)
    trace.provider = resolved.provider_name
    trace.model = resolved.provider.model
    trace.key_source = resolved.key_source
    if resolved.key_source == keys.KEY_DEFAULT:
        keys.spend_default_key(user)

    known = schema.get_schema(workspace, include_samples=True)
    schema_text = schema.render(known)

    done = generate_and_run(
        resolved.provider,
        question,
        schema_text,
        check=lambda sql: guard.check(sql, known),
        execute=lambda sql: runner.run(sql, workspace),
        trace=trace,
        schema_name=workspace.schema_name,
    )
    return AskResult(
        question=question,
        sql=done.sql,
        columns=done.result.columns,
        rows=done.result.rows,
        row_count=done.result.row_count,
        truncated=done.result.truncated,
        confidence=done.confidence,
        check=done.check,
        rationale=done.rationale,
        model=resolved.provider.model,
        latency_ms=trace.latency_ms,
    )


@dataclass(frozen=True)
class Generated:
    """What the core path produced: the SQL that ran and its result."""

    sql: str
    result: runner.QueryResult
    confidence: float
    check: str
    rationale: str


def generate_and_run(
    provider: LLMProvider,
    question: str,
    schema_text: str,
    *,
    check: Callable[[str], guard.GuardResult],
    execute: Callable[[str], runner.QueryResult],
    trace: Trace,
    dialect: str = prompt.DIALECT_POSTGRES,
    schema_name: str = DEMO_SCHEMA,
) -> Generated:
    """The core of an ask, with no user, key or log: prompt, LLM, parse, check,
    run, and the repair loop. `check` and `execute` are the guard and the runner
    for the database being asked (Postgres for users, SQLite for Spider evals).
    Raises a typed AppException; `trace` collects tokens, attempts and the SQL."""
    system = prompt.system_prompt(dialect, schema_name)
    text = prompt.build_prompt(question, schema_text)
    max_attempts = 1 + settings.ASK_MAX_REPAIR_ATTEMPTS
    for attempt in range(1, max_attempts + 1):
        trace.attempts = attempt
        try:
            reply = provider.generate(
                LLMRequest(prompt=text, system=system, json_output=True)
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
            checked = check(parsed.sql)
            trace.sql = checked.sql
            result = execute(checked.sql)
        except (GuardRejected, QueryFailed) as error:
            if attempt == max_attempts:
                raise
            text = prompt.build_repair_prompt(
                question, schema_text, trace.sql, error.detail
            )
            continue
        break

    trace.confidence = confidence.score(
        guard=checked.report,
        revisions=trace.attempts - 1,
        row_count=result.row_count,
        truncated=result.truncated,
    )
    trace.row_count = result.row_count
    return Generated(
        sql=checked.sql,
        result=result,
        confidence=trace.confidence,
        check=confidence.label(
            guard=checked.report,
            row_count=result.row_count,
            truncated=result.truncated,
        ),
        rationale=parsed.rationale,
    )
