"""Scores the agent on a target: one run per question, approved automatically.

An eval has no human, so each pause is approved by the harness and recorded as
actor `eval` in the trace. The final SQL is then scored by the same comparison
as the ask path. The model never sees gold SQL or gold rows."""

import time
from collections.abc import Callable

from django.conf import settings

from accounts.models import User
from agent import loop, prompts, service
from agent.errors import CODE_NOT_ANSWERABLE
from agent.models import AgentRun, AgentStep
from ask import service as ask_service
from ask.errors import QueryFailed, QueryTimeout
from common.llm import LLMProvider
from evals.models import EvalResult
from evals.runner import RETRY_CODES, Outcome, _judge
from evals.targets.base import EvalQuestion, Target

EVAL_USER_EMAIL = "evals@querylab.invalid"
KEY_SOURCE_EVAL = "eval"


def eval_user() -> User:
    """The account eval runs belong to. Email is not unique, so look before creating."""
    user = User.objects.filter(email=EVAL_USER_EMAIL).first()
    return user or User.objects.create_user(EVAL_USER_EMAIL)


def _new_run(user: User, question: EvalQuestion, provider: LLMProvider) -> AgentRun:
    return AgentRun.objects.create(
        user=user,
        question=question.question,
        provider=provider.provider,
        model=provider.model,
        key_source=KEY_SOURCE_EVAL,
        prompt_version=prompts.PROMPT_VERSION,
    )


def drive(run: AgentRun, provider: LLMProvider) -> AgentRun:
    """Run to the end, approving every pause. Bounded by the run's own budgets:
    each approval follows a proposal, and proposals are capped."""
    loop.advance(run.pk, provider)
    run.refresh_from_db()
    while run.status == AgentRun.STATUS_AWAITING_APPROVAL:
        service.decide(run, service.DECISION_APPROVE, actor=AgentStep.ACTOR_EVAL)
        loop.advance(run.pk, provider)
        run.refresh_from_db()
    return run


def agent_once(
    target: Target,
    question: EvalQuestion,
    provider: LLMProvider,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> Outcome:
    """Run the agent on one question, starting over after a provider hiccup."""
    user = eval_user()
    for retry in range(settings.EVAL_LLM_RETRIES + 1):
        run = drive(_new_run(user, question, provider), provider)
        if run.error_code in RETRY_CODES and retry < settings.EVAL_LLM_RETRIES:
            sleep(settings.EVAL_RETRY_BACKOFF_SECONDS * 2**retry)
            continue
        return outcome_of(target, question, run)
    raise AssertionError("unreachable")  # pragma: no cover


def _base(run: AgentRun, outcome: str, reason: str) -> Outcome:
    return Outcome(
        outcome=outcome,
        reason=reason,
        predicted_sql=run.final_sql,
        confidence=run.confidence,
        attempts=run.llm_calls,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        steps=run.step_count,
        llm_calls=run.llm_calls,
        revisions=run.revisions,
        agent_run_id=run.pk,
    )


def outcome_of(target: Target, question: EvalQuestion, run: AgentRun) -> Outcome:
    if run.status == AgentRun.STATUS_SUCCEEDED:
        # The rows were not stored; run the approved SQL again for the comparison.
        # This is the harness reading its own run, not part of the agent.
        result = target.execute(question)(run.final_sql)
        trace = ask_service.Trace(question=question.question)
        trace.attempts = run.llm_calls
        trace.input_tokens, trace.output_tokens = run.input_tokens, run.output_tokens
        done = ask_service.Generated(
            sql=run.final_sql,
            result=result,
            confidence=run.confidence or 0.0,
            check=run.check_label,
            rationale="",
        )
        judged = _judge(target, question, trace, done)
        judged.steps, judged.llm_calls = run.step_count, run.llm_calls
        judged.revisions, judged.agent_run_id = run.revisions, run.pk
        return judged
    code = run.error_code
    if code == CODE_NOT_ANSWERABLE:
        if question.answerable:
            return _base(run, EvalResult.OUTCOME_NOT_ANSWERABLE, "declined")
        return _base(run, EvalResult.OUTCOME_CORRECT, "correctly_declined")
    if code == QueryTimeout.error_code:
        return _base(run, EvalResult.OUTCOME_TIMEOUT, "")
    if code == QueryFailed.error_code:
        return _base(run, EvalResult.OUTCOME_ERROR, code)
    if code.startswith("llm_"):
        return _base(run, EvalResult.OUTCOME_LLM_FAILED, code)
    return _base(run, EvalResult.OUTCOME_ERROR, code or run.status)
