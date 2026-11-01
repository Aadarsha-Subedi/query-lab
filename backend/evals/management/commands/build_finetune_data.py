import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from ask import schema
from evals.models import EvalRun
from evals.targets import olist, spider
from finetune import dataset

HELP_TEXT = """\
Spider train is not unpacked. Put train_spider.json from the Spider 1.0 download
next to dev.json in infra/data/spider/ (database/ already holds every database)."""


class Command(BaseCommand):
    help = "Write instruction JSONL for the LoRA fine-tune (offline, never committed)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--out", help="Output directory (default FINETUNE_OUTPUT_DIR)."
        )
        parser.add_argument(
            "--train-file", help="Default: <EVAL_SPIDER_DIR>/train_spider.json."
        )

    def handle(self, *args: object, **options: object) -> None:
        out = Path(str(options["out"] or settings.FINETUNE_OUTPUT_DIR))
        train_file = Path(
            str(options["train_file"] or spider.root() / "train_spider.json")
        )
        if not train_file.exists():
            raise CommandError(HELP_TEXT)

        assignment = spider.load_split()
        held_out = {
            db for db, half in assignment.items() if half == EvalRun.SPLIT_HELD_OUT
        }
        train = dataset.examples_from_spider(
            json.loads(train_file.read_text()), source="spider-train"
        )
        tune = [
            dataset.Example(q.id, q.db_id, q.question, q.gold_sql, "spider-tune")
            for q in spider.SpiderTarget().questions(EvalRun.SPLIT_TUNE)
        ]
        examples = dataset.dedupe([*train, *tune])

        benchmark = [
            q.question for q in spider.SpiderTarget().questions(EvalRun.SPLIT_HELD_OUT)
        ]
        benchmark += [item["question"] for item in olist.read_golden()]
        examples, dropped = dataset.drop_benchmark_questions(examples, benchmark)
        try:
            dataset.assert_no_leakage(
                examples, banned_dbs=held_out, banned_questions=benchmark
            )
        except dataset.LeakageError as error:
            raise CommandError(str(error)) from None

        cap = settings.FINETUNE_MAX_EXAMPLES
        examples = dataset.shuffled(examples, settings.FINETUNE_SEED)
        if cap:
            examples = examples[:cap]
        train_set, validation = dataset.split_by_database(
            examples, settings.FINETUNE_VALIDATION_FRACTION, settings.FINETUNE_SEED
        )

        cache: dict[str, str] = {}

        def schema_for(db_id: str) -> str:
            if db_id not in cache:
                cache[db_id] = schema.render(spider.read_schema(db_id), qualify=False)
            return cache[db_id]

        files = {
            "train.jsonl": dataset.dump_jsonl(
                dataset.build_records(train_set, schema_for)
            ),
            "validation.jsonl": dataset.dump_jsonl(
                dataset.build_records(validation, schema_for)
            ),
        }
        out.mkdir(parents=True, exist_ok=True)
        for name, text in files.items():
            (out / name).write_text(text)
        manifest = {
            "seed": settings.FINETUNE_SEED,
            "base_model": settings.FINETUNE_BASE_MODEL,
            "dropped_benchmark_questions": dropped,
            "sources": sorted({e.source for e in examples}),
            "train_examples": len(train_set),
            "validation_examples": len(validation),
            "train_databases": sorted({e.db_id for e in train_set}),
            "validation_databases": sorted({e.db_id for e in validation}),
            "sha256": {name: dataset.sha256(text) for name, text in files.items()},
        }
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        self.stdout.write(
            f"Wrote {len(train_set)} train and {len(validation)} validation examples to {out} "
            f"({dropped} dropped for sharing a question text with the benchmark)."
        )
