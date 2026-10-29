from django.core.management.base import BaseCommand

from core import datadb


class Command(BaseCommand):
    help = (
        "Apply infra/sql/*.sql to the data database (querylab) in order: the demo "
        "schema, the read-only reader role and its grants. Safe to re-run."
    )

    def handle(self, *args: object, **options: object) -> None:
        files = datadb.sql_files()
        datadb.apply(files, datadb.placeholders())
        for path in files:
            self.stdout.write(f"applied {path.name}")
        self.stdout.write(self.style.SUCCESS("Data database bootstrapped."))
