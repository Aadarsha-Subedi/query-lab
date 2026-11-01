"""Typed errors of the trace workbench. Messages are generic: they never carry SQL
or another person's question."""

from common.exception.domain import (
    ConflictException,
    NotFoundException,
    UnprocessableEntityException,
)


class CaseNotFound(NotFoundException):
    message = "Trace case not found."
    error_code = "case_not_found"


class CaseNotReviewable(ConflictException):
    message = "Only a drafted case can be approved, rejected or marked unanswerable."
    error_code = "case_not_reviewable"


class DraftUnusable(UnprocessableEntityException):
    message = "The draft failed its checks. Send corrected SQL to approve this case."
    error_code = "draft_unusable"
