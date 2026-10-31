"""Write the OpenAPI document of the one NinjaAPI to a file, sorted and indented
so diffs stay small. The frontend generates its types from this file, and CI
regenerates it and fails when it differs from the committed one."""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from ninja.responses import NinjaJSONEncoder

from config.api import api


def render() -> str:
    return (
        json.dumps(
            api.get_openapi_schema(),
            cls=NinjaJSONEncoder,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )


class Command(BaseCommand):
    help = "Write the OpenAPI document to a file (default openapi.json)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--output", default="openapi.json")

    def handle(self, *args: Any, **options: Any) -> None:
        Path(options["output"]).write_text(render())
        self.stdout.write(f"Wrote {options['output']}")
