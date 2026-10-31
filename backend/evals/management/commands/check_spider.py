from django.core.management.base import BaseCommand, CommandError

from evals.targets import spider

HELP_TEXT = """\
Spider is not unpacked yet. To set it up:
  1. Download "Spider 1.0" from https://yale-lily.github.io/spider (a zip of about 1 GB).
  2. Unpack it so that infra/data/spider/ holds dev.json and database/ (the
     per-database folders). It is licensed CC BY-SA 4.0 and is never committed.
  3. Run this command again."""


class Command(BaseCommand):
    help = "Check that Spider is unpacked, and that every dev database is in the split."

    def handle(self, *args: object, **options: object) -> None:
        try:
            counts = spider.SpiderTarget().question_counts()
        except spider.SpiderNotFound:
            raise CommandError(HELP_TEXT) from None
        assignment = spider.load_split()
        missing_files = [db for db in counts if not spider.database_path(db).exists()]
        missing_split = sorted(set(counts) - set(assignment))
        unused = sorted(set(assignment) - set(counts))
        self.stdout.write(
            f"{sum(counts.values())} dev questions in {len(counts)} databases."
        )
        for half in ("tune", "held-out"):
            dbs = [
                db for db, name in assignment.items() if name == half and db in counts
            ]
            self.stdout.write(
                f"  {half}: {len(dbs)} databases, {sum(counts[d] for d in dbs)} questions"
            )
        problems = []
        if missing_files:
            problems.append(f"Database files missing: {missing_files}")
        if missing_split:
            problems.append(
                f"Not in spider_split.json: {missing_split}. Suggested split: "
                f"{spider.build_split(counts)}"
            )
        if unused:
            problems.append(f"In spider_split.json but not in dev.json: {unused}")
        if problems:
            raise CommandError("\n".join(problems))
        self.stdout.write(self.style.SUCCESS("Spider looks ready."))
