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
    # The key asks use when the user's AI source is "own". At most one per user.
    is_active = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider"], name="unique_llm_key_per_provider"
            ),
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_active=True),
                name="one_active_llm_key_per_user",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id}:{self.provider}"


class UserAISetting(TimeStampModel):
    """Which AI a user's questions use: QueryLab's shared key (daily limit) or their own
    active key. No row means QueryLab's AI."""

    SOURCE_QUERYLAB = "querylab"
    SOURCE_OWN = "own"
    SOURCES = (SOURCE_QUERYLAB, SOURCE_OWN)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_setting"
    )
    source = models.CharField(max_length=10, default=SOURCE_QUERYLAB)
    # The Gemini model used on QueryLab's key; blank means the default model.
    querylab_model = models.CharField(max_length=100, blank=True, default="")

    def __str__(self) -> str:
        return f"{self.user_id}:{self.source}"


class AskLog(TimeStampModel):
    """One row per ask, success or failure. Holds the question and the SQL that
    ran, never the result rows. These rows seed the traces of steps 3 and 6."""

    STATUS_OK = "ok"
    STATUS_GUARD_REJECTED = "guard_rejected"
    STATUS_QUERY_FAILED = "query_failed"
    STATUS_LLM_FAILED = "llm_failed"
    STATUS_TIMEOUT = "timeout"
    STATUS_NOT_ANSWERABLE = "not_answerable"
    STATUS_REFUSED = "refused"  # bad question or the default-key limit

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ask_logs"
    )
    question = models.TextField()
    sql = models.TextField(blank=True)
    status = models.CharField(max_length=20)
    error_code = models.CharField(max_length=50, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    provider = models.CharField(max_length=20, blank=True)
    model = models.CharField(max_length=100, blank=True)
    key_source = models.CharField(max_length=10, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    confidence = models.FloatField(null=True, blank=True)
    row_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]
