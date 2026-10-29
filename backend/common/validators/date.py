from datetime import date

from common.exception.domain import ValidationException
from common.validators.constants import (
    INVALID_DATE_RANGE_CODE,
    INVALID_DATE_RANGE_MESSAGE,
)


def validate_date_range(
    start: date | None, end: date | None, field: str = "end_date"
) -> None:
    """Raise an API ValidationException on `field` when both dates are set and
    `end` falls before `start`."""
    if start and end and end < start:
        raise ValidationException(
            errors=[{"field": field, "message": INVALID_DATE_RANGE_MESSAGE}],
            error_code=INVALID_DATE_RANGE_CODE,
        )
