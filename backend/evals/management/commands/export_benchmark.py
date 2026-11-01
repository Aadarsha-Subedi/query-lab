import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError, CommandParser

from ask import prompt
from evals import predictions
from evals.models import EvalRun
from evals.targets import olist, spider
from evals.targets.base import Target


class Command(BaseCommand):
    help = (
        "Write the benchmark questions a Colab notebook must answer (step 7): "
        "the prompts the model is shown, never gold SQL or rows."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--out", required=True, help="File to write (JSONL).")

    def handle(self, *args: object, **options: object) -> None:
        targets: list[tuple[Target, str]] = [
            (spider.SpiderTarget(), EvalRun.SPLIT_HELD_OUT),
            (olist.OlistTarget(), EvalRun.SPLIT_ALL),
        ]
        lines = []
        try:
            for target, split in targets:
                system = prompt.system_prompt(target.dialect)
                for question in target.questions(split):
                    text = predictions.user_prompt(
                        prompt.clean_question(question.question),
                        target.schema_text(question),
                    )
                    lines.append(
                        {
                            "id": f"{target.name}:{question.id}",
                            "target": target.name,
                            "system": system,
                            "prompt": text,
                            "prompt_sha256": predictions.prompt_hash(text),
                        }
                    )
        except spider.SpiderNotFound as error:
            raise CommandError(str(error)) from None
        path = Path(str(options["out"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(line) + "\n" for line in lines))
        self.stdout.write(f"Wrote {len(lines)} benchmark prompts to {path}.")
