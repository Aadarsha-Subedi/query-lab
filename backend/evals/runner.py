"""Scores a model on a target: ask each question, run both SQL strings, compare.

One question at a time, written to the database as it completes so a crashed run
can be resumed. Never sends gold SQL or gold rows to the model."""

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from ask import prompt, service
from ask.errors import (
    GuardRejected,
    LLMFailed,
    NotAnswerable,
    QueryFailed,
    QueryTimeout,
)
from common.exception.domain import AppException
from common.llm import LLMProvider, allowed_models, create_provider
from common.llm.constants import PROVIDER_GROQ, PROVIDER_OPENAI
from evals import compare
from evals.models import EvalResult, EvalRun
from evals.targets.base import EvalQuestion, Target

logger = logging.getLogger(__name__)

# Provider hiccups worth another try; a bad key or a bad answer is not.
RETRY_CODES = {"llm_rate_limited", "llm_unavailable", "llm_timeout"}


class EvalConfigError(Exception):
    """A model or key the harness cannot use."""


def build_provider(model: str) -> tuple[str, LLMProvider]:
    """The provider for `model`, from the harness keys in .env (no user keys)."""
    for provider, key in (
        (PROVIDER_GROQ, settings.QUERY_LAB_API_KEY),
        (PROVIDER_OPENAI, settings.EVAL_OPENAI_API_KEY),
    ):
        if model in allowed_models(provider):
            return provider, create_provider(provider, key, model)
    raise EvalConfigError(f"Model not in LLM_GROQ_MODELS or LLM_OPENAI_MODELS: {model}")


@dataclass
class Outcome:
    outcome: str
    reason: str = ""
    predicted_sql: str = ""
    confidence: float | None = None
    attempts: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    # Agent runner only.
    steps: int = 0
    llm_calls: int = 0
    revisions: int = 0
    agent_run_id: int | None = None


def _error_outcome(error: AppException) -> tuple[str, str]:
    if isinstance(error, GuardRejected):
        return EvalResult.OUTCOME_GUARD_REJECTED, error.detail[:200]
    if isinstance(error, QueryTimeout):
        return EvalResult.OUTCOME_TIMEOUT, ""
    if isinstance(error, QueryFailed):
        return EvalResult.OUTCOME_ERROR, error.detail[:200]
    if isinstance(error, LLMFailed):
        return EvalResult.OUTCOME_LLM_FAILED, error.error_code
    return EvalResult.OUTCOME_ERROR, error.error_code


def ask_once(
    target: Target,
    question: EvalQuestion,
    provider: LLMProvider,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> Outcome:
    """Ask the model, retrying a provider rate limit with backoff."""
    schema_text = target.schema_text(question)
    for retry in range(settings.EVAL_LLM_RETRIES + 1):
        trace = service.Trace(question=question.question)
        try:
            done = service.generate_and_run(
                provider,
                question.question,
                schema_text,
                check=target.check(question),
                execute=target.execute(question),
                trace=trace,
                dialect=target.dialect,
            )
        except LLMFailed as error:
            if error.error_code in RETRY_CODES and retry < settings.EVAL_LLM_RETRIES:
                sleep(settings.EVAL_RETRY_BACKOFF_SECONDS * 2**retry)
                continue
            return _failed(trace, *_error_outcome(error))
        except NotAnswerable:
            outcome = (
                EvalResult.OUTCOME_NOT_ANSWERABLE
                if question.answerable
                else EvalResult.OUTCOME_CORRECT
            )
            reason = "declined" if question.answerable else "correctly_declined"
            return _failed(trace, outcome, reason)
        except AppException as error:
            return _failed(trace, *_error_outcome(error))
        return _judge(target, question, trace, done)
    raise AssertionError("unreachable")  # pragma: no cover


def _failed(trace: service.Trace, outcome: str, reason: str) -> Outcome:
    return Outcome(
        outcome=outcome,
        reason=reason,
        predicted_sql=trace.sql,
        attempts=trace.attempts,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
    )


def _judge(
    target: Target,
    question: EvalQuestion,
    trace: service.Trace,
    done: service.Generated,
) -> Outcome:
    base = Outcome(
        outcome=EvalResult.OUTCOME_WRONG,
        predicted_sql=done.sql,
        confidence=done.confidence,
        attempts=trace.attempts,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
    )
    if not question.answerable:
        base.reason = "answered_unanswerable"
        return base
    try:
        gold = target.gold_rows(question)
    except AppException as error:
        base.outcome = EvalResult.OUTCOME_ERROR
        base.reason = f"gold_failed:{error.error_code}"
        return base
    verdict = compare.compare(
        gold,
        done.result.rows,
        ordered=compare.gold_is_ordered(question.gold_sql, target.dialect),
        as_set=getattr(target, "compare_as_set", False),
    )
    base.reason = verdict.reason
    if verdict.match:
        base.outcome = EvalResult.OUTCOME_CORRECT
    return base


def pick_questions(
    questions: list[EvalQuestion], *, limit: int | None, seed: int
) -> list[EvalQuestion]:
    if limit is None or limit >= len(questions):
        return questions
    chosen = set(random.Random(seed).sample(range(len(questions)), limit))
    return [q for i, q in enumerate(questions) if i in chosen]


def run_eval(
    target: Target,
    *,
    split: str,
    provider_name: str,
    provider: LLMProvider,
    questions: list[EvalQuestion],
    run: EvalRun | None = None,
    runner_name: str = EvalRun.RUNNER_ASK,
    progress: Callable[[int, int, EvalQuestion, Outcome], None] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> EvalRun:
    """Score `questions`; continue `run` if given (questions already stored are skipped).
    `runner_name` picks the one-shot ask path or the agent loop (auto-approved)."""
    ask_one = ask_once
    prompt_version = prompt.PROMPT_VERSION
    if runner_name == EvalRun.RUNNER_AGENT:
        from agent import prompts as agent_prompts
        from evals import agent_runner

        ask_one = agent_runner.agent_once
        prompt_version = agent_prompts.PROMPT_VERSION
    if run is None:
        run = EvalRun.objects.create(
            target=target.name,
            split=split,
            provider=provider_name,
            model=provider.model,
            prompt_version=prompt_version,
            runner=runner_name,
        )
    done_ids = set(run.results.values_list("question_id", flat=True))
    todo = [q for q in questions if q.id not in done_ids]
    try:
        for index, question in enumerate(todo, start=1):
            if index > 1:
                sleep(settings.EVAL_CALL_DELAY_SECONDS)  # stay under the rate limit
            started = time.perf_counter()
            outcome = ask_one(target, question, provider, sleep=sleep)
            EvalResult.objects.create(
                run=run,
                question_id=question.id,
                tags=question.tags,
                question=question.question,
                gold_sql=question.gold_sql,
                predicted_sql=outcome.predicted_sql,
                outcome=outcome.outcome,
                reason=outcome.reason,
                confidence=outcome.confidence,
                attempts=outcome.attempts,
                input_tokens=outcome.input_tokens,
                output_tokens=outcome.output_tokens,
                latency_ms=int((time.perf_counter() - started) * 1000),
                agent_run_id=outcome.agent_run_id,
                steps=outcome.steps,
                llm_calls=outcome.llm_calls,
                revisions=outcome.revisions,
                trace_case_id=question.case_id,
                cluster_key=question.cluster,
            )
            if progress:
                progress(index, len(todo), question, outcome)
    except BaseException:
        run.status = EvalRun.STATUS_FAILED
        run.save(update_fields=["status", "updated_at"])
        raise
    run.question_count = run.results.count()
    run.correct_count = run.results.filter(outcome=EvalResult.OUTCOME_CORRECT).count()
    run.status = EvalRun.STATUS_DONE
    run.finished_at = timezone.now()
    run.save()
    return run
