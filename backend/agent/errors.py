"""Typed errors for the agent. As in `ask.errors`, messages are generic: they never
carry SQL, a prompt, a key or result rows. `ToolError` is different: it is not an
API error but a message for the model, so it can say what went wrong in a tool call."""

from common.exception.domain import (
    AppException,
    ConflictException,
    NotFoundException,
    ThrottledException,
)


class ToolError(Exception):
    """A tool call that cannot run (unknown tool, bad input, unknown table, SQL the
    guard refuses). Fed back to the model, counted against the budget."""


class RunNotFound(NotFoundException):
    message = "Run not found."
    error_code = "run_not_found"


class RunNotAwaitingApproval(ConflictException):
    message = "This run is not waiting for approval."
    error_code = "run_not_awaiting_approval"


class RunExpired(ConflictException):
    message = "This run waited too long for approval and expired."
    error_code = "run_expired"


class RunLimitReached(ThrottledException):
    message = "You have too many unfinished runs. Finish or cancel one first."
    error_code = "agent_run_limit"


class StreamLimitReached(ThrottledException):
    message = "Too many live streams are open. Poll the run instead."
    error_code = "agent_stream_limit"


class AgentFailed(AppException):
    """A run ended on its own limits or a model failure. `error_code` says which."""

    status_code = 422
    message = "The agent could not finish this run."
    error_code = "agent_failed"


class BudgetExceeded(AgentFailed):
    message = "The run used up its budget."
    error_code = "agent_budget_exceeded"
