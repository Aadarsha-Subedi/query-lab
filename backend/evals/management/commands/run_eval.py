import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from ask import prompt
from common.llm import LLMProvider
from evals import gate, predictions, runner, scoring
from evals.models import EvalRun
from evals.targets import olist, spider, traces
from evals.targets.base import EvalQuestion, Target


class Command(BaseCommand):
    help = (
        "Score a model on a question set (execution accuracy). Run it in the dev "
        "container: make eval ARGS='run_eval --target olist --model codestral-2508'"
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--target", choices=["olist", "spider", "traces"], required=True
        )
        parser.add_argument(
            "--model", help="The model to ask (not used with --predictions)."
        )
        parser.add_argument(
            "--predictions",
            help="Score answers from a JSONL file written elsewhere (step 7) instead "
            "of calling a model. The run's model is the file's label.",
        )
        parser.add_argument(
            "--runner",
            choices=[EvalRun.RUNNER_ASK, EvalRun.RUNNER_AGENT],
            default=EvalRun.RUNNER_ASK,
            help="ask: the one-shot /api/ask path. agent: the step 3 agent, with every "
            "pause approved by the harness (Olist and traces).",
        )
        parser.add_argument(
            "--split",
            choices=[EvalRun.SPLIT_ALL, EvalRun.SPLIT_TUNE, EvalRun.SPLIT_HELD_OUT],
            help="Spider: tune or held-out (default held-out). Olist: all.",
        )
        parser.add_argument("--limit", type=int, help="Ask only a random sample.")
        parser.add_argument("--seed", type=int, default=0, help="Seed for --limit.")
        parser.add_argument("--resume", type=int, help="Continue this run id.")
        parser.add_argument(
            "--retry-failed",
            action="store_true",
            help="With --resume: also ask again the questions that ended in llm_failed.",
        )
        parser.add_argument("--yes", action="store_true", help="Skip the cost guard.")
        parser.add_argument(
            "--gate",
            action="store_true",
            help="Compare this run with a baseline and exit 1 when accuracy drops by "
            "more than EVAL_GATE_MAX_DROP_POINTS (or too few cases are shared).",
        )
        parser.add_argument(
            "--baseline",
            type=int,
            help="With --gate: the run to compare with (default: the latest done run "
            "of the same target, split, runner and prompt version).",
        )
        parser.add_argument(
            "--include-unreviewed",
            action="store_true",
            help="Olist: also ask questions whose gold SQL you have not reviewed.",
        )

    def handle(self, *args: object, **options: object) -> None:
        target_name = str(options["target"])
        split = options["split"] or (
            EvalRun.SPLIT_HELD_OUT if target_name == "spider" else EvalRun.SPLIT_ALL
        )
        target: Target
        if target_name == "spider":
            target = spider.SpiderTarget()
        elif target_name == "traces":
            target = traces.TraceTarget()
        else:
            target = olist.OlistTarget(
                include_unreviewed=bool(options["include_unreviewed"])
            )
        runner_name = str(options["runner"])
        if runner_name == EvalRun.RUNNER_AGENT and target_name == "spider":
            raise CommandError(
                "The agent runner works on Olist and traces: it uses the Postgres guard and "
                "reader. Spider stays on --runner ask."
            )
        provider: LLMProvider
        try:
            if options["predictions"]:
                file = predictions.load(Path(str(options["predictions"])))
                provider_name = predictions.PROVIDER_NAME
                provider = predictions.FilePredictionProvider(file)
            elif options["model"]:
                provider_name, provider = runner.build_provider(str(options["model"]))
            else:
                raise CommandError("Give --model or --predictions.")
            questions = runner.pick_questions(
                target.questions(str(split)),
                limit=options["limit"],  # type: ignore[arg-type]
                seed=int(options["seed"]),  # type: ignore[call-overload]
            )
        except (
            runner.EvalConfigError,
            predictions.PredictionsError,
            spider.SpiderNotFound,
            ValueError,
        ) as error:
            raise CommandError(str(error)) from None
        if not questions:
            raise CommandError(
                "No questions to ask (Olist: review the gold SQL first; traces: approve cases first)."
            )

        if options["predictions"]:
            self._check_coverage(target, questions, file)

        if options["baseline"] and not options["gate"]:
            raise CommandError("--baseline needs --gate.")
        baseline = self._baseline(options) if options["gate"] else None

        run = None
        if options["resume"]:
            try:
                run = EvalRun.objects.get(pk=int(options["resume"]))  # type: ignore[call-overload]
            except EvalRun.DoesNotExist:
                raise CommandError("No such run to resume.") from None
            if (run.target, run.split, run.model, run.runner) != (
                target_name,
                split,
                provider.model,
                runner_name,
            ):
                raise CommandError(
                    "That run used a different target, split, model or runner."
                )
            if options["retry_failed"]:
                removed, _ = run.results.filter(outcome="llm_failed").delete()
                self.stdout.write(f"Dropped {removed} llm_failed results to ask again.")
        elif options["retry_failed"]:
            raise CommandError("--retry-failed needs --resume.")

        # The agent makes several LLM calls per question; count the budget's worst case.
        calls = len(questions) * (
            settings.AGENT_MAX_LLM_CALLS if runner_name == EvalRun.RUNNER_AGENT else 1
        )
        self.stdout.write(
            f"{len(questions)} questions to ask {provider_name}/{provider.model} "
            f"on {target_name}/{split} with the {runner_name} runner "
            f"(up to {calls} LLM calls)."
        )
        if calls > settings.EVAL_CONFIRM_ABOVE_CALLS and not options["yes"]:
            raise CommandError(
                f"That is more than EVAL_CONFIRM_ABOVE_CALLS "
                f"({settings.EVAL_CONFIRM_ABOVE_CALLS}) LLM calls. Add --yes to go on."
            )

        def progress(
            index: int, total: int, question: EvalQuestion, outcome: runner.Outcome
        ) -> None:
            self.stdout.write(f"[{index}/{total}] {question.id} {outcome.outcome}")

        try:
            run = runner.run_eval(
                target,
                split=str(split),
                provider_name=provider_name,
                provider=provider,
                questions=questions,
                run=run,
                runner_name=runner_name,
                progress=progress,
                sleep=(lambda _: None) if options["predictions"] else time.sleep,
            )
        except spider.SpiderNotFound as error:
            raise CommandError(str(error)) from None
        self.stdout.write("")
        self.stdout.write(scoring.format_report(run))
        if baseline is None and options["gate"]:
            baseline = gate.latest_baseline(run)
        if options["gate"]:
            self._gate(run, baseline)

    def _check_coverage(
        self,
        target: Target,
        questions: list[EvalQuestion],
        file: predictions.PredictionsFile,
    ) -> None:
        """Every question must have an answer in the file before anything is scored."""
        missing = [
            q.id
            for q in questions
            if predictions.prompt_hash(
                predictions.user_prompt(
                    prompt.clean_question(q.question), target.schema_text(q)
                )
            )
            not in file.answers
        ]
        if missing:
            raise CommandError(
                f"{len(missing)} of {len(questions)} questions have no answer in the "
                f"file (first: {', '.join(missing[:5])}). Export the benchmark again "
                "and regenerate, or use --limit/--split to match the file."
            )

    def _baseline(self, options: dict) -> EvalRun | None:
        """The run named by --baseline, checked before any LLM call. Without it the
        latest matching run is looked up after the run (its prompt version is only
        known then)."""
        if options["baseline"]:
            try:
                return EvalRun.objects.get(pk=int(options["baseline"]))
            except EvalRun.DoesNotExist:
                raise CommandError("No such baseline run.") from None
        return None

    def _gate(self, run: EvalRun, baseline: EvalRun | None) -> None:
        if baseline is None:
            raise CommandError(
                "GATE FAILED: no earlier finished run of this target, split, runner "
                "and prompt version to compare with. Run once without --gate to set "
                "a baseline, or pass --baseline ID."
            )
        try:
            verdict = gate.evaluate(run, baseline)
        except gate.NotComparable as error:
            raise CommandError(f"GATE FAILED: {error}") from None
        self.stdout.write("")
        self.stdout.write(gate.format_verdict(verdict, run, baseline))
        if not verdict.passed:
            raise CommandError("Gate failed.")
