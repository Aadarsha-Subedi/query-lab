from django.core.management.base import BaseCommand, CommandError

from evals import agent_runner, drafting
from evals.runner import EvalConfigError


class Command(BaseCommand):
    help = (
        "Draft expected SQL for the next batch of trace cases (TRACES_DRAFT_MAX_PER_BATCH, "
        "one LLM call each, counted on the eval account). Run it in the dev container."
    )

    def handle(self, *args: object, **options: object) -> None:
        try:
            done = drafting.draft_batch(agent_runner.eval_user())
        except EvalConfigError as error:
            raise CommandError(str(error)) from None
        self.stdout.write(f"{done} cases drafted.")
