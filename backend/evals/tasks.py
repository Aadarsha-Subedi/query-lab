"""Huey tasks for the trace workbench. Drafting is one job per batch."""

from huey.contrib.djhuey import db_task

from accounts.models import User
from evals import drafting


@db_task()
def draft_batch(user_id: int) -> int:
    """Draft the next batch of trace cases; the calls count against `user_id`."""
    return drafting.draft_batch(User.objects.get(pk=user_id))
