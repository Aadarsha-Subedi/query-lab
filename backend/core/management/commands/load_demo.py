from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.db import connections
from psycopg import sql

from core import demo


class Command(BaseCommand):
    help = (
        "Load the Olist CSVs into the demo schema (truncates first; safe to re-run). "
        "Reads DEMO_DATA_DIR and shifts dates by DEMO_DATE_SHIFT_DAYS."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--source",
            type=Path,
            help="Directory with the CSVs (defaults to the DEMO_DATA_DIR setting).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        source = options["source"] or Path(settings.DEMO_DATA_DIR)
        counts = demo.load(source, settings.DEMO_DATE_SHIFT_DAYS)
        # Fresh statistics: the ask schema reader takes example values from them.
        with connections[settings.DATA_DB_ALIAS].cursor() as cursor:
            for table in counts:
                cursor.execute(
                    sql.SQL("ANALYZE {}.{}").format(
                        sql.Identifier(demo.DEMO_SCHEMA), sql.Identifier(table)
                    )
                )
        for table, count in counts.items():
            self.stdout.write(f"{table}: {count} rows")
        self.stdout.write(self.style.SUCCESS("Demo data loaded."))
