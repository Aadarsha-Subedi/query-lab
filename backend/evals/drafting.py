"""Draft the expected SQL for a trace case with an LLM (step 6).

The draft is untrusted model output and never gold: it passes `guard.check` and
runs on the reader before a person sees it, and a person still approves or
edits it (evals/review.py). The prompt holds the question, the schema text and,
when the user edited the SQL, the SQL they approved. It never holds result rows.
One call per case that stands for a cluster, never one per run."""

import logging

from django.conf import settings
from django.utils import timezone

from accounts.models import User
from ask import guard, keys, prompt, runner, schema
from ask.errors import DefaultKeyLimitReached, GuardRejected, QueryFailed, QueryTimeout
from common.exception.domain import AppException
from common.llm import LLMError, LLMProvider, LLMRequest
from evals import runner as eval_runner
from evals.models import TraceCase

logger = logging.getLogger(__name__)

ERROR_MAX_CHARS = 300


def build_draft_prompt(case: TraceCase, schema_text: str) -> str:
    text = prompt.build_prompt(case.question, schema_text)
    if TraceCase.REASON_EDITED in case.reasons.split(",") and case.source_sql:
        text += (
            "\n\nThe person who asked changed the query to this one before running it. "
            "Treat it as a hint about what they wanted; it may still be wrong.\n"
            f"<approved_sql>\n{case.source_sql}\n</approved_sql>"
        )
    return text


def _error_text(error: AppException) -> str:
    detail = getattr(error, "detail", "") or error.error_code
    return prompt.first_line(str(detail))[:ERROR_MAX_CHARS]


def draft_case(case: TraceCase, provider: LLMProvider, schema_text: str) -> TraceCase:
    """One LLM call, then guard and run the answer. A failure is stored on the case
    as `draft_error`; nothing is raised for a bad draft."""
    known = schema.get_schema(include_samples=True)
    case.draft_model = provider.model
    case.draft_sql = ""
    case.draft_error = ""
    try:
        reply = provider.generate(
            LLMRequest(
                prompt=build_draft_prompt(case, schema_text),
                system=prompt.system_prompt(),
                json_output=True,
            )
        )
        parsed = prompt.parse_reply(reply.text)
    except LLMError as error:
        # A provider hiccup: keep it a candidate so the next batch tries again.
        case.draft_error = error.code
        case.save(update_fields=["draft_model", "draft_error", "updated_at"])
        return case
    if not parsed.answerable:
        case.draft_error = prompt.first_line(f"declined: {parsed.rationale}")[
            :ERROR_MAX_CHARS
        ]
    else:
        case.draft_sql = parsed.sql
        try:
            checked = guard.check(parsed.sql, known)
            case.draft_sql = checked.sql
            runner.run(checked.sql)  # the rows are dropped; only success matters
        except (GuardRejected, QueryFailed, QueryTimeout) as error:
            case.draft_error = _error_text(error)
    case.status = TraceCase.STATUS_DRAFTED
    case.drafted_at = timezone.now()
    case.save(
        update_fields=[
            "draft_sql",
            "draft_model",
            "draft_error",
            "status",
            "drafted_at",
            "updated_at",
        ]
    )
    return case


def to_draft() -> list[TraceCase]:
    """The cases to draft next: candidates, most signals first, then newest, at
    most TRACES_DRAFT_MAX_PER_BATCH."""
    return list(
        TraceCase.objects.filter(status=TraceCase.STATUS_CANDIDATE).order_by(
            "-signals", "-source_created_at", "-id"
        )[: settings.TRACES_DRAFT_MAX_PER_BATCH]
    )


def draft_batch(user: User, provider: LLMProvider | None = None) -> int:
    """Draft the next batch. Each call counts as one spend of the default key for
    `user`, like every other LLM call; the batch stops when that limit is used up.
    Returns how many cases got a draft (or a stored error)."""
    if provider is None:
        _, provider = eval_runner.build_provider(settings.TRACES_DRAFT_MODEL)
    schema_text = schema.render(schema.get_schema(include_samples=True))
    done = 0
    for case in to_draft():
        try:
            keys.spend_default_key(user)
        except DefaultKeyLimitReached:
            logger.info("trace drafting stopped: the default key limit is used up")
            break
        draft_case(case, provider, schema_text)
        if case.status == TraceCase.STATUS_DRAFTED:
            done += 1
    return done
