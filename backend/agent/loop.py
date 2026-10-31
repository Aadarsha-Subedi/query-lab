"""The agent loop: `advance(run_id)` takes turns until the run must stop.

    plan -> act turns (tool calls) -> propose_sql -> PAUSE (awaiting_approval)
         -> [user approves / edits / cancels] -> execute -> reflect? -> finish

It stops on a pause, a finish, a give-up, a budget limit or an error, saves its
state and returns, so a paused run holds no thread and no worker. Execution is
not a tool: the loop alone calls `runner.run`, and only for SQL a person approved
(or an eval auto-approved). The model never gets to skip that."""

import logging
import time
from typing import Any

import sqlglot
from django.conf import settings
from sqlglot import exp

from agent import confidence, events, prompts, state, tools, trace
from agent.errors import (
    CODE_INTERNAL,
    CODE_KEY_CHANGED,
    CODE_LLM_CALLS,
    CODE_NOT_ANSWERABLE,
    CODE_REVISIONS,
    CODE_STEPS,
    CODE_TIMEOUT,
    CODE_TOKENS,
    RunStop,
    ToolError,
)
from agent.models import AgentRun, AgentStep
from agent.prompts import ReplyError
from agent.tools.base import ToolContext
from agent.tools.list_tables import table_infos
from ask import keys, runner, schema
from ask.errors import QueryFailed, QueryTimeout
from ask.guard import GuardReport
from ask.prompt import first_line
from common.llm import LLMError, LLMProvider, LLMRequest

logger = logging.getLogger(__name__)

TRIGGER_ERROR = "error"
TRIGGER_EMPTY = "empty"
TRIGGER_TRUNCATED = "truncated"
TRIGGER_SINGLE_VALUE = "single_value"
TRIGGER_ALWAYS = "always"


def advance(run_id: int) -> None:
    """Carry a run forward until it pauses or ends. Safe to call twice: a run that
    another worker holds, or that is not `running`, is left alone."""
    with state.run_lock(run_id) as acquired:
        if not acquired:
            return
        run = AgentRun.objects.select_related("user").get(pk=run_id)
        if run.status != AgentRun.STATUS_RUNNING:
            return
        Loop(run).go()


def result_summary(result: runner.QueryResult) -> dict[str, Any]:
    """What the model, the trace and a replay see of a result: never all rows."""
    return {
        "columns": result.columns,
        "row_count": result.row_count,
        "truncated": result.truncated,
        "preview": result.rows[: settings.AGENT_RESULT_PREVIEW_ROWS],
    }


def result_trigger(result: runner.QueryResult) -> str | None:
    """The cheap rule check that decides whether the model should read a result."""
    if result.row_count == 0:
        return TRIGGER_EMPTY
    if result.truncated:
        return TRIGGER_TRUNCATED
    if result.row_count == 1 and len(result.columns) == 1:
        return TRIGGER_SINGLE_VALUE
    if settings.AGENT_REFLECT_ALWAYS:
        return TRIGGER_ALWAYS
    return None


def has_text_filter(sql: str) -> bool:
    """Does the query compare against a string literal in a WHERE clause?"""
    try:
        tree = sqlglot.parse_one(sql, read="postgres")
    except sqlglot.errors.SqlglotError:
        return False
    return any(
        literal.is_string
        for where in tree.find_all(exp.Where)
        for literal in where.find_all(exp.Literal)
    )


class Loop:
    def __init__(self, run: AgentRun):
        self.run = run
        self.started = time.monotonic()
        self.base_ms = run.latency_ms
        # Tokens and time of LLM calls since the last recorded step.
        self.call_in = 0
        self.call_out = 0
        self.call_ms = 0
        self.state = state.load(run)
        self.provider: LLMProvider | None = None
        self.known: schema.Schema | None = None

    # ── driving ──────────────────────────────────────────────────────────

    def go(self) -> None:
        try:
            self._connect()
            while self.run.status == AgentRun.STATUS_RUNNING:
                self._turn()
        except RunStop as stop:
            self._fail(stop)
        except Exception:  # a bug must end the run, not strand it
            logger.exception("Agent run %s crashed", self.run.pk)
            self._fail(RunStop(CODE_INTERNAL, "The run hit an unexpected error."))
        finally:
            self._settle()

    def _turn(self) -> None:
        phase = self.state.phase
        if phase == state.PHASE_PLAN:
            self._plan()
        elif phase == state.PHASE_ACT:
            self._act()
        elif phase == state.PHASE_EXECUTE:
            self._execute()
        elif phase == state.PHASE_REFLECT:
            self._reflect()
        else:
            self._finish()

    def _connect(self) -> None:
        resolved = keys.resolve_provider(self.run.user)
        if (resolved.provider_name, resolved.key_source) != (
            self.run.provider,
            self.run.key_source,
        ):
            raise RunStop(CODE_KEY_CHANGED, "The LLM key changed while the run waited.")
        self.provider = resolved.provider
        self.known = schema.get_schema(include_samples=True)

    def _settle(self) -> None:
        """Add the time spent, and keep or drop the saved state."""
        self.run.latency_ms = self.base_ms + int(
            (time.monotonic() - self.started) * 1000
        )
        self.run.save(update_fields=["latency_ms", "updated_at"])
        if self.run.is_terminal:
            state.delete(self.run.pk)
        else:
            state.save(self.state)

    # ── budgets ──────────────────────────────────────────────────────────

    def _elapsed_seconds(self) -> float:
        return self.base_ms / 1000 + (time.monotonic() - self.started)

    def _check_budget(self, *, llm: bool = False, step: bool = True) -> None:
        run = self.run
        if self._elapsed_seconds() >= settings.AGENT_RUN_TIMEOUT_SECONDS:
            raise RunStop(CODE_TIMEOUT, "The run took too long.")
        if run.input_tokens + run.output_tokens >= settings.AGENT_MAX_TOKENS:
            raise RunStop(CODE_TOKENS, "The run used up its token budget.")
        if llm and run.llm_calls >= settings.AGENT_MAX_LLM_CALLS:
            raise RunStop(CODE_LLM_CALLS, "The run used up its model calls.")
        if step and run.step_count >= settings.AGENT_MAX_STEPS:
            raise RunStop(CODE_STEPS, "The run used up its steps.")

    def _budget_text(self) -> str:
        run = self.run
        return (
            f"{settings.AGENT_MAX_STEPS - run.step_count} steps, "
            f"{settings.AGENT_MAX_LLM_CALLS - run.llm_calls} model calls, "
            f"{settings.AGENT_MAX_REVISIONS - run.revisions} SQL revisions."
        )

    # ── the model ────────────────────────────────────────────────────────

    def _llm(self, system: str, text: str) -> str:
        assert self.provider is not None
        self._check_budget(llm=True)
        started = time.monotonic()
        try:
            reply = self.provider.generate(
                LLMRequest(prompt=text, system=system, json_output=True)
            )
        except LLMError as error:
            self.run.llm_calls += 1
            self.run.save(update_fields=["llm_calls", "updated_at"])
            raise RunStop(error.code, error.message) from None
        self.run.llm_calls += 1
        self.run.input_tokens += reply.input_tokens
        self.run.output_tokens += reply.output_tokens
        self.run.save(
            update_fields=["llm_calls", "input_tokens", "output_tokens", "updated_at"]
        )
        self.call_in += reply.input_tokens
        self.call_out += reply.output_tokens
        self.call_ms += int((time.monotonic() - started) * 1000)
        return reply.text

    def _ask(self, system: str, text: str, parse: Any) -> Any:
        """One call that must return something `parse` accepts; a bad reply is told
        why and asked again, up to AGENT_MAX_PARSE_RETRIES (each is an LLM call)."""
        attempt = 0
        while True:
            reply = self._llm(system, text)
            try:
                return parse(reply)
            except ReplyError as error:
                if attempt >= settings.AGENT_MAX_PARSE_RETRIES:
                    raise RunStop(
                        "llm_bad_response", "The model's reply could not be used."
                    ) from None
                attempt += 1
                text += "\n\n" + prompts.REPLY_FORMAT_NOTE.format(reason=str(error))

    def _step(self, kind: str, **fields: Any) -> AgentStep:
        """Record a step, carrying the tokens and time of the model calls behind it."""
        fields.setdefault("input_tokens", self.call_in)
        fields.setdefault("output_tokens", self.call_out)
        fields.setdefault("latency_ms", self.call_ms)
        self.call_in = self.call_out = self.call_ms = 0
        self._check_budget(llm=False)
        return trace.record_step(self.run, kind, **fields)

    def _remember(self, label: str, payload: str) -> None:
        self.state.history.append(
            prompts.history_entry(label, payload, settings.AGENT_STEP_OUTPUT_MAX_CHARS)
        )

    # ── phases ───────────────────────────────────────────────────────────

    def _context(self) -> ToolContext:
        assert self.known is not None
        return ToolContext(schema=self.known, executed=self.state.executed)

    def _schema_text(self) -> str:
        assert self.known is not None
        if settings.AGENT_FULL_SCHEMA_START:
            return schema.render(self.known)
        return prompts.tables_text(table_infos(self._context()))

    def _plan(self) -> None:
        plan = self._ask(
            prompts.PLAN_SYSTEM,
            prompts.plan_prompt(self.run.question, self._schema_text()),
            prompts.parse_plan,
        )
        self.state.plan = plan.text()
        self.state.assumptions = plan.assumptions
        self.state.phase = state.PHASE_ACT
        self.run.plan = self.state.plan
        self.run.save(update_fields=["plan", "updated_at"])
        self._step(
            AgentStep.KIND_PLAN,
            input={"assumptions": plan.assumptions},
            output=self.state.plan,
        )

    def _act(self) -> None:
        turn = self._ask(
            prompts.act_system(),
            prompts.act_prompt(
                self.run.question,
                self._schema_text(),
                self.state.plan,
                self.state.history,
                self._budget_text(),
            ),
            prompts.parse_turn,
        )
        self._call_tool(turn.tool, turn.input)

    def _call_tool(self, name: str, raw_input: dict[str, Any]) -> None:
        started = time.monotonic()
        try:
            if (
                name == "propose_sql"
                and self.state.proposals > 0
                and self.run.revisions >= settings.AGENT_MAX_REVISIONS
            ):
                raise RunStop(CODE_REVISIONS, "The run used up its SQL revisions.")
            tool, output = tools.call(name, raw_input, self._context())
        except ToolError as error:
            self._step(
                AgentStep.KIND_TOOL,
                tool_name=name,
                input=raw_input,
                output=str(error),
                status=AgentStep.STATUS_ERROR,
                error_code="tool_error",
            )
            self._remember(f"{name} error", str(error))
            return
        data = output.model_dump()
        self._step(
            AgentStep.KIND_TOOL,
            tool_name=name,
            input=raw_input,
            output=trace.dump(data),
            latency_ms=self.call_ms + int((time.monotonic() - started) * 1000),
        )
        if name == "sample_values":
            self.state.samples_checked.append(f"{data['table']}.{data['column']}")
        if tool.needs_approval:
            self._pause(data)
        elif tool.terminal and name == "give_up":
            raise RunStop(CODE_NOT_ANSWERABLE, data["reason"][:300])
        elif tool.terminal:
            self.state.answer = data["answer"]
            self.state.phase = state.PHASE_FINISH
        else:
            self._remember(name, trace.dump(data))

    def _pause(self, proposal: dict[str, Any]) -> None:
        """Hand the proposed SQL to the user and stop. Nothing runs from here."""
        run, st = self.run, self.state
        if st.proposals > 0:
            run.revisions += 1
        st.proposals += 1
        st.pending_sql = proposal["sql"]
        st.pending_rationale = proposal["rationale"]
        st.pending_rewrites = proposal["guard_rewrites"]
        st.edited = False
        st.decided_by = ""
        st.phase = state.PHASE_EXECUTE
        self._step(
            AgentStep.KIND_APPROVAL,
            input={
                "sql": st.pending_sql,
                "rationale": st.pending_rationale,
                "assumptions": st.assumptions,
                "guard_rewrites": st.pending_rewrites,
                "revision": run.revisions,
            },
            output="Waiting for approval.",
        )
        run.status = AgentRun.STATUS_AWAITING_APPROVAL
        run.save(update_fields=["status", "revisions", "updated_at"])
        events.publish_status(run.pk)

    def _execute(self) -> None:
        st, run = self.state, self.run
        if not st.decided_by:  # cannot happen: only a decision moves a run here
            raise RunStop("agent_not_approved", "The SQL was not approved.")
        sql = st.pending_sql
        started = time.monotonic()
        try:
            result = runner.run(sql)
        except QueryTimeout:
            self._step(
                AgentStep.KIND_EXECUTE,
                input={"sql": sql, "edited": st.edited},
                output="The query took too long and was stopped.",
                status=AgentStep.STATUS_ERROR,
                error_code=QueryTimeout.error_code,
                actor=st.decided_by,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            raise RunStop(QueryTimeout.error_code, QueryTimeout.message) from None
        except QueryFailed as error:
            st.last_error = first_line(error.detail)
            self._step(
                AgentStep.KIND_EXECUTE,
                input={"sql": sql, "edited": st.edited},
                output=st.last_error,
                status=AgentStep.STATUS_ERROR,
                error_code=QueryFailed.error_code,
                actor=st.decided_by,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            st.phase = state.PHASE_REFLECT
            return
        summary = result_summary(result)
        st.executed = True
        st.last_error = ""
        st.truncated = result.truncated
        st.last_summary = trace.dump(summary)
        run.final_sql = sql
        run.row_count = result.row_count
        run.save(update_fields=["final_sql", "row_count", "updated_at"])
        self._step(
            AgentStep.KIND_EXECUTE,
            input={"sql": sql, "edited": st.edited},
            output=st.last_summary,
            actor=st.decided_by,
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        st.trigger = result_trigger(result) or ""
        if st.trigger:
            st.phase = state.PHASE_REFLECT
        else:
            if st.reflect_ok is None:
                st.reflect_ok = True  # the rule check passed: nothing to look at
            st.phase = state.PHASE_FINISH

    def _reflect(self) -> None:
        st = self.state
        error = st.last_error
        trigger = TRIGGER_ERROR if error else (st.trigger or TRIGGER_ALWAYS)
        reflection = self._ask(
            prompts.REFLECT_SYSTEM,
            prompts.reflect_prompt(
                self.run.question, st.pending_sql, st.last_summary, error
            ),
            prompts.parse_reflection,
        )
        if st.reflect_ok is None and not error:
            st.reflect_ok = reflection.verdict == "ok"
        self._step(
            AgentStep.KIND_REFLECT,
            input={"trigger": trigger, "sql": st.pending_sql},
            output=trace.dump(
                {
                    "verdict": reflection.verdict,
                    "reason": reflection.reason,
                    "revised_sql": reflection.revised_sql,
                }
            ),
        )
        if reflection.verdict == "ok" and not error:
            st.phase = state.PHASE_FINISH
        elif reflection.verdict == "ok":
            raise RunStop(
                QueryFailed.error_code, "The query failed and could not be fixed."
            )
        elif reflection.revised_sql:
            self._remember("reflect", f"revise: {reflection.reason}")
            st.phase = state.PHASE_ACT
            self._call_tool(
                "propose_sql",
                {"sql": reflection.revised_sql, "rationale": reflection.reason},
            )
        else:
            self._remember("reflect", f"revise: {reflection.reason}")
            st.phase = state.PHASE_ACT

    def _finish(self) -> None:
        st, run = self.state, self.run
        guard = GuardReport(tuple(st.pending_rewrites))
        score = confidence.score(
            guard=guard,
            revisions=run.revisions,
            row_count=run.row_count,
            truncated=st.truncated,
            reflect_ok=st.reflect_ok,
            samples_checked=(
                bool(st.samples_checked) if has_text_filter(run.final_sql) else None
            ),
        )
        label = confidence.label(
            guard=guard,
            row_count=run.row_count,
            truncated=st.truncated,
            reflect_ok=st.reflect_ok,
        )
        run.confidence = score
        run.check_label = label
        answer = (
            st.answer
            or st.pending_rationale
            or f"The query returned {run.row_count} rows."
        )
        trace.close_run(
            run,
            AgentRun.STATUS_SUCCEEDED,
            output=answer,
            detail={"check": label, "revisions": run.revisions},
        )

    def _fail(self, stop: RunStop) -> None:
        trace.close_run(
            self.run, AgentRun.STATUS_FAILED, output=stop.message, error_code=stop.code
        )
