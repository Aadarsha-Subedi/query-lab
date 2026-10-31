from django.conf import settings
from django.db import models

from common.models import TimeStampModel


class UserLLMKey(TimeStampModel):
    """A user's own API key for one provider, encrypted at rest (common.crypto).
    The key is never returned by the API; only its last four characters are."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="llm_keys"
    )
    provider = models.CharField(max_length=20)
    encrypted_key = models.TextField()
    key_last4 = models.CharField(max_length=4)
    model = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider"], name="unique_llm_key_per_provider"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.provider}"
