from abc import ABC, abstractmethod
from typing import Any


class BaseValidator(ABC):
    """Contract every custom validator follows: a callable object that
    raises ValidationError when `value` is invalid."""

    message: str = "Invalid value."

    @abstractmethod
    def __call__(self, value: Any) -> None:
        """Raise ValidationError if invalid. Return None (implicitly) if valid."""
