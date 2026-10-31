from django.core.management.base import BaseCommand, CommandParser

from ask import guard, runner, schema
from common.exception.domain import AppException
from evals.targets import olist


class Command(BaseCommand):
    help = (
        "Show each Olist gold query with the rows it returns, so you can check it "
        "answers its question. --mark-reviewed then sets reviewed on all of them."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--mark-reviewed", action="store_true")
        parser.add_argument("--rows", type=int, default=3, help="Rows shown per query.")

    def handle(self, *args: object, **options: object) -> None:
        if options["mark_reviewed"]:
            count = olist.mark_reviewed()
            self.stdout.write(f"Marked {count} questions as reviewed.")
            return
        known = schema.get_schema(include_samples=True)
        shown = int(options["rows"])  # type: ignore[call-overload]
        for item in olist.read_golden():
            flag = "reviewed" if item["reviewed"] else "NOT reviewed"
            self.stdout.write(f"\n{item['id']} [{item['tags']}] ({flag})")
            self.stdout.write(f"Q: {item['question']}")
            if not item["answerable"]:
                self.stdout.write("   (unanswerable: the model should decline)")
                continue
            self.stdout.write(f"SQL: {item['gold_sql']}")
            try:
                checked = guard.check(item["gold_sql"], known)
                result = runner.run(checked.sql)
            except AppException as error:
                self.stdout.write(self.style.ERROR(f"   FAILS: {error.error_code}"))
                continue
            self.stdout.write(f"   {result.row_count} rows, columns {result.columns}")
            for row in result.rows[:shown]:
                self.stdout.write(f"   {row}")
