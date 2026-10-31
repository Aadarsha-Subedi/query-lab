from django.conf import settings
from django.db import models

from common.models import TimeStampModel


class EvalRun(TimeStampModel):
    """One scored pass of a model over a question set. Made from the command line
    by the owner, so it has no user."""

    TARGET_OLIST = "olist"
    TARGET_SPIDER = "spider"

    RUNNER_ASK = "ask"  # the one-shot /api/ask path (step 1)
    RUNNER_AGENT = "agent"  # the agent loop (step 3), auto-approved

    SPLIT_ALL = "all"
    SPLIT_TUNE = "tune"
    SPLIT_HELD_OUT = "held-out"

    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"

    target = models.CharField(max_length=20)
    split = models.CharField(max_length=20, default=SPLIT_ALL)
    provider = models.CharField(max_length=20)
    model = models.CharField(max_length=100)
    prompt_version = models.CharField(max_length=20)
    runner = models.CharField(max_length=10, default=RUNNER_ASK)
    question_count = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, default=STATUS_RUNNING)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"{self.target}/{self.split} {self.model} #{self.pk}"


class EvalResult(TimeStampModel):
    """One question of a run. Holds the question and both SQL strings, never the
    rows either query returned."""

    OUTCOME_CORRECT = "correct"
    OUTCOME_WRONG = "wrong"
    OUTCOME_ERROR = "error"
    OUTCOME_TIMEOUT = "timeout"
    OUTCOME_GUARD_REJECTED = "guard_rejected"
    OUTCOME_NOT_ANSWERABLE = "not_answerable"
    OUTCOME_LLM_FAILED = "llm_failed"

    run = models.ForeignKey(EvalRun, on_delete=models.CASCADE, related_name="results")
    question_id = models.CharField(max_length=100)
    tags = models.CharField(max_length=200, blank=True)
    question = models.TextField()
    gold_sql = models.TextField()
    predicted_sql = models.TextField(blank=True)
    outcome = models.CharField(max_length=20)
    reason = models.CharField(max_length=200, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(default=0)
    # Agent runner only: the run behind this result and what it cost.
    agent_run = models.ForeignKey(
        "agent.AgentRun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    steps = models.PositiveSmallIntegerField(default=0)
    llm_calls = models.PositiveSmallIntegerField(default=0)
    revisions = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "question_id"], name="unique_result_per_question"
            )
        ]

    def __str__(self) -> str:
        return f"{self.run_id}:{self.question_id}:{self.outcome}"


class TraceCase(TimeStampModel):
    """A stored agent run picked as an eval case (step 6). Nothing here is gold
    until a person approves it: the model's `draft_sql` is only a starting point and
    `gold_sql` is set on approval alone. Holds SQL and the question text, never
    result rows. `source_run_id` is a plain number so the run may disappear later."""

    STATUS_CANDIDATE = "candidate"  # picked by a rule, not drafted yet
    STATUS_DRAFTED = "drafted"  # a draft (or its error) is waiting for a person
    STATUS_APPROVED = "approved"  # a person approved the gold SQL
    STATUS_REJECTED = "rejected"
    STATUSES = (STATUS_CANDIDATE, STATUS_DRAFTED, STATUS_APPROVED, STATUS_REJECTED)

    # Why the run was picked (comma separated, see evals/candidates.py).
    REASON_EDITED = "edited"
    REASON_THUMBS_DOWN = "thumbs_down"
    REASON_FAILED = "failed"
    REASON_REVISED = "revised"
    REASON_NOT_ANSWERABLE = "not_answerable"
    REASON_NEEDS_LOOK = "needs_look"

    # What the run ended as, for clustering.
    OUTCOME_ANSWERED = "answered"
    OUTCOME_DECLINED = "declined"
    OUTCOME_ERROR = "error"
    OUTCOME_UNFINISHED = "unfinished"

    source_run_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    source_created_at = models.DateTimeField()
    question = models.TextField()
    reasons = models.CharField(max_length=200)
    signals = models.PositiveSmallIntegerField(default=0)
    outcome = models.CharField(max_length=12)
    # The SQL the run ended with, or proposed first when it ended without any.
    source_sql = models.TextField(blank=True)
    status = models.CharField(max_length=10, default=STATUS_CANDIDATE)
    cluster_key = models.CharField(max_length=60, blank=True)
    draft_sql = models.TextField(blank=True)
    draft_model = models.CharField(max_length=100, blank=True)
    draft_error = models.CharField(max_length=300, blank=True)
    drafted_at = models.DateTimeField(null=True, blank=True)
    gold_sql = models.TextField(blank=True)
    answerable = models.BooleanField(default=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-source_created_at", "-id"]
        indexes = [models.Index(fields=["status", "cluster_key"])]

    def __str__(self) -> str:
        return f"case {self.pk} ({self.status})"
