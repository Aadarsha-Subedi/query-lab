from django.core.management.base import BaseCommand, CommandError, CommandParser

from evals import confidence_analysis
from evals.models import EvalRun


class Command(BaseCommand):
    help = (
        "Check the agent's confidence features and score against a finished agent "
        "eval run: which features separate right from wrong, and whether the score "
        "passes the acceptance rule (CONFIDENCE_MIN_SEPARATION). Read-only."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--run", type=int, help="An agent EvalRun id.")
        parser.add_argument(
            "--cases",
            action="store_true",
            help="Use the reviewed (approved) trace cases as labels instead of a run.",
        )

    def handle(self, *args: object, **options: object) -> None:
        if bool(options["cases"]) == bool(options["run"]):
            raise CommandError("Give exactly one of --run ID or --cases.")
        if options["cases"]:
            analysis_of_cases = confidence_analysis.analyse_cases()
            self.stdout.write(
                confidence_analysis.format_case_analysis(analysis_of_cases)
            )
            return
        try:
            run = EvalRun.objects.get(pk=int(options["run"]))  # type: ignore[call-overload]
        except EvalRun.DoesNotExist:
            raise CommandError("No such run.") from None
        if run.runner != EvalRun.RUNNER_AGENT:
            raise CommandError("That run did not use the agent runner.")
        analysis = confidence_analysis.analyse(run)
        self.stdout.write(confidence_analysis.format_analysis(run, analysis))
