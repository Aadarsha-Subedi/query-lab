from django.core.management.base import BaseCommand, CommandError, CommandParser

from evals import scoring
from evals.models import EvalRun


class Command(BaseCommand):
    help = "Print the report of a stored run, or two runs side by side with --compare."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--run", type=int)
        parser.add_argument("--compare", type=int, nargs=2, metavar=("A", "B"))
        parser.add_argument("--list", action="store_true", help="List recent runs.")

    def handle(self, *args: object, **options: object) -> None:
        if options["list"]:
            for run in EvalRun.objects.all()[:20]:
                self.stdout.write(
                    f"#{run.pk} {run.target}/{run.split} {run.model} "
                    f"{run.correct_count}/{run.question_count} [{run.status}]"
                )
            return
        if options["compare"]:
            first, second = (self._get(pk) for pk in options["compare"])  # type: ignore[attr-defined]
            a, b = scoring.summarise(first), scoring.summarise(second)
            self.stdout.write(
                f"{'':22}{'#' + str(first.pk):>14}{'#' + str(second.pk):>14}"
            )
            rows = [
                ("model", first.model, second.model),
                (
                    "target/split",
                    f"{first.target}/{first.split}",
                    f"{second.target}/{second.split}",
                ),
                ("prompt", first.prompt_version, second.prompt_version),
                ("accuracy", f"{a.accuracy:.1%}", f"{b.accuracy:.1%}"),
                ("correct", f"{a.correct}/{a.total}", f"{b.correct}/{b.total}"),
                ("mean latency ms", a.mean_latency_ms, b.mean_latency_ms),
                ("cost USD", a.cost_usd, b.cost_usd),
            ]
            for label, left, right in rows:
                self.stdout.write(f"{label:22}{left!s:>14}{right!s:>14}")
            return
        if not options["run"]:
            raise CommandError("Give --run ID, --compare A B or --list.")
        self.stdout.write(scoring.format_report(self._get(options["run"])))  # type: ignore[arg-type]

    @staticmethod
    def _get(pk: int) -> EvalRun:
        try:
            return EvalRun.objects.get(pk=pk)
        except EvalRun.DoesNotExist:
            raise CommandError(f"No run #{pk}.") from None
