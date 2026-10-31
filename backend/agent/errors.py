"""Typed errors for the agent. As in `ask.errors`, messages are generic: they never
carry SQL, a prompt, a key or result rows. `ToolError` is different: it is not an
API error but a message for the model, so it can say what went wrong in a tool call."""

from common.exception.domain import (
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


class RunStop(Exception):
    """Raised inside the loop to end a run as failed. `code` is the typed error
    code stored on the run; `message` is a short, generic line for the trace."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# Error codes stored on a failed run (besides the ask-path ones: query_failed,
# query_timeout, guard_rejected, and the llm_* codes from common.llm).
CODE_STEPS = "agent_steps_exceeded"
CODE_LLM_CALLS = "agent_llm_calls_exceeded"
CODE_TOKENS = "agent_tokens_exceeded"
CODE_REVISIONS = "agent_revisions_exceeded"
CODE_TIMEOUT = "agent_timeout"
CODE_WORKER_LOST = "agent_worker_lost"
CODE_KEY_CHANGED = "llm_key_changed"
CODE_NOT_ANSWERABLE = "not_answerable"
CODE_INTERNAL = "agent_internal_error"
