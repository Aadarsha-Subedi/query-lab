from django.core.validators import EmailValidator as DjangoEmailValidator

from common.validators.base import BaseValidator


class EmailValidator(BaseValidator):
    """Wraps Django's own EmailValidator — the same one EmailField uses."""

    message = "Enter a valid email address."

    def __init__(self, message: str | None = None):
        self.message = message or self.message
        self._django_validator = DjangoEmailValidator(message=self.message)

    def __call__(self, value: str) -> None:
        self._django_validator(value)
