"""Typed errors for the ask path. Messages are generic on purpose: they never
contain the model's SQL, a prompt or a key. `GuardRejected` and `QueryFailed`
carry a short `detail` that goes back to the model on a repair retry, never to
the client."""

import math
from datetime import UTC, datetime, timedelta

from common.exception.domain import (
    AppException,
    BadRequestException,
    ThrottledException,
    UnprocessableEntityException,
)


class QuestionInvalid(BadRequestException):
    message = "The question is empty or too long."
    error_code = "question_invalid"


class GuardRejected(BadRequestException):
    message = "The generated query was not allowed to run."
    error_code = "guard_rejected"

    def __init__(self, detail: str):
        super().__init__()
        self.detail = detail


class QueryFailed(UnprocessableEntityException):
    message = "The generated query could not be run."
    error_code = "query_failed"

    def __init__(self, detail: str):
        super().__init__()
        self.detail = detail


class QueryTimeout(AppException):
    status_code = 504
    message = "The query took too long and was stopped."
    error_code = "query_timeout"


class LLMFailed(AppException):
    status_code = 502
    message = "The AI request failed."
    error_code = "llm_error"


class DefaultKeyLimitReached(ThrottledException):
    message = "The daily limit on QueryLab's shared key is reached. Add your own key to keep asking."
    error_code = "default_key_limit"

    def __init__(self) -> None:
        super().__init__()
        # The daily count restarts at midnight UTC (ask/keys.py).
        now = datetime.now(UTC)
        midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self.retry_after = max(1, math.ceil((midnight - now).total_seconds()))
        self.headers = {"Retry-After": str(self.retry_after)}


class NotAnswerable(UnprocessableEntityException):
    """The model says the schema cannot answer this question. The message is
    the model's own explanation (it never contains SQL or data)."""

    message = "This question cannot be answered from the available data."
    error_code = "not_answerable"
