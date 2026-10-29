from typing import Any

from django.conf import settings
from django.contrib.auth.password_validation import (
    CommonPasswordValidator,
    MinimumLengthValidator,
    NumericPasswordValidator,
    UserAttributeSimilarityValidator,
)
from django.core.exceptions import ValidationError

from common.exception.domain import ValidationException
from common.validators.base import BaseValidator
from common.validators.constants import (
    NEEDS_LOWERCASE_MESSAGE,
    NEEDS_UPPERCASE_MESSAGE,
    NEW_PASSWORD_MUST_DIFFER_MESSAGE,
)


class MixedCaseValidator:
    """Django password validator (AUTH_PASSWORD_VALIDATORS): at least one
    upper- and one lower-case letter. allauth runs it on signup and resets."""

    def validate(self, password: str, user: Any = None) -> None:
        errors = []
        if not any(c.isupper() for c in password):
            errors.append(ValidationError(NEEDS_UPPERCASE_MESSAGE, code="no_upper"))
        if not any(c.islower() for c in password):
            errors.append(ValidationError(NEEDS_LOWERCASE_MESSAGE, code="no_lower"))
        if errors:
            raise ValidationError(errors)

    def get_help_text(self) -> str:
        return "Your password must mix upper- and lower-case letters."


class PasswordValidator(BaseValidator):
    """Callable validator. Pass `user` (any object with email/name attributes)
    to also reject passwords too similar to the user's own details."""

    message = "Password does not meet security requirements."

    def __init__(self, user: object | None = None) -> None:
        self.user = user
        self.validators: list[Any] = [
            MinimumLengthValidator(min_length=settings.PASSWORD_MIN_LENGTH),
            CommonPasswordValidator(),
            NumericPasswordValidator(),
            MixedCaseValidator(),
        ]
        if user is not None:
            self.validators.append(UserAttributeSimilarityValidator())

    def __call__(self, value: str) -> None:
        errors = []

        for validator in self.validators:
            try:
                validator.validate(value, self.user)
            except ValidationError as e:
                errors.extend(e.messages)

        if errors:
            raise ValidationError(errors)


def validate_password_strength(
    password: str, user: object | None = None, field: str = "password"
) -> None:
    """Run PasswordValidator and report failures as an API ValidationException
    pointing at `field`."""
    try:
        PasswordValidator(user=user)(password)
    except ValidationError as exc:
        raise ValidationException(
            errors=[{"field": field, "message": message} for message in exc.messages]
        ) from exc


def validate_password_changed(
    user: Any, new_password: str, field: str = "new_password"
) -> None:
    """Raise an API ValidationException on `field` when `new_password` equals
    the user's current password. `user` needs `check_password`."""
    if user.check_password(new_password):
        raise ValidationException(
            errors=[{"field": field, "message": NEW_PASSWORD_MUST_DIFFER_MESSAGE}]
        )
