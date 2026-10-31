from django.conf import settings
from django.db import models

from common.models import TimeStampModel


class IllegalTransition(Exception):
    """A status change the run's lifecycle does not allow."""


class AgentRun(TimeStampModel):
    """One question answered by the agent. The durable trace is its steps; Redis
    only holds working state while the run is active (agent/state.py). Result
    rows are never stored: see AgentStep.output."""

    STATUS_RUNNING = "running"
    STATUS_AWAITING_APPROVAL = "awaiting_approval"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"

    TERMINAL = (STATUS_SUCCEEDED, STATUS_FAILED, STATUS_CANCELLED, STATUS_EXPIRED)
    ACTIVE = (STATUS_RUNNING, STATUS_AWAITING_APPROVAL)
    TRANSITIONS = {
        STATUS_RUNNING: {
            STATUS_AWAITING_APPROVAL,
            STATUS_SUCCEEDED,
            STATUS_FAILED,
            STATUS_CANCELLED,
        },
        STATUS_AWAITING_APPROVAL: {
            STATUS_RUNNING,
            STATUS_CANCELLED,
            STATUS_EXPIRED,
            STATUS_FAILED,
        },
    }

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_runs"
    )
    question = models.TextField()
    status = models.CharField(max_length=20, default=STATUS_RUNNING)
    error_code = models.CharField(max_length=50, blank=True)
    provider = models.CharField(max_length=20)
    model = models.CharField(max_length=100)
    key_source = models.CharField(max_length=10)
    prompt_version = models.CharField(max_length=20)
    plan = models.TextField(blank=True)
    final_sql = models.TextField(blank=True)
    row_count = models.PositiveIntegerField(default=0)
    # Null when there is no score to show; `check_label` is the plain-words version.
    confidence = models.FloatField(null=True, blank=True)
    check_label = models.CharField(max_length=20, blank=True)
    step_count = models.PositiveSmallIntegerField(default=0)
    llm_calls = models.PositiveSmallIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    # Time the agent worked, in ms; the wait for approval is not counted.
    latency_ms = models.PositiveIntegerField(default=0)
    revisions = models.PositiveSmallIntegerField(default=0)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "updated_at"]),
        ]

    def __str__(self) -> str:
        return f"run {self.pk} ({self.status})"

    @property
    def is_terminal(self) -> bool:
        return self.status in self.TERMINAL

    def save(self, *args, **kwargs) -> None:
        """Refuse a status change the lifecycle forbids (for example a finished run
        going back to running). The check reads the stored status, so it also holds
        for two writers."""
        if self.pk is not None:
            stored = (
                type(self).objects.filter(pk=self.pk).values_list("status", flat=True)
            ).first()
            if (
                stored is not None
                and stored != self.status
                and self.status not in self.TRANSITIONS.get(stored, set())
            ):
                raise IllegalTransition(f"{stored} -> {self.status}")
        super().save(*args, **kwargs)


class AgentStep(TimeStampModel):
    """One thing the agent did, in order: a plan, a tool call, the approval pause,
    the execution, a reflection, the end. `output` is trimmed to
    AGENT_STEP_OUTPUT_MAX_CHARS and, for an execution, holds the columns, row
    count and a short preview. The preview is stored on purpose, so a replay shows
    what the user saw without running any SQL again."""

    KIND_PLAN = "plan"
    KIND_TOOL = "tool"
    KIND_APPROVAL = "approval"
    KIND_EXECUTE = "execute"
    KIND_REFLECT = "reflect"
    KIND_FINAL = "final"
    KINDS = (
        KIND_PLAN,
        KIND_TOOL,
        KIND_APPROVAL,
        KIND_EXECUTE,
        KIND_REFLECT,
        KIND_FINAL,
    )

    STATUS_OK = "ok"
    STATUS_ERROR = "error"

    ACTOR_AGENT = "agent"
    ACTOR_USER = "user"
    ACTOR_EVAL = "eval"

    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name="steps")
    index = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=10)
    tool_name = models.CharField(max_length=40, blank=True)
    input = models.JSONField(default=dict, blank=True)
    output = models.TextField(blank=True)
    status = models.CharField(max_length=10, default=STATUS_OK)
    error_code = models.CharField(max_length=50, blank=True)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    actor = models.CharField(max_length=10, default=ACTOR_AGENT)

    class Meta:
        ordering = ["run_id", "index"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "index"], name="unique_step_index_per_run"
            )
        ]

    def __str__(self) -> str:
        return f"{self.run_id}#{self.index} {self.kind}"
