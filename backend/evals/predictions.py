"""Score answers that were written elsewhere (step 7: a model run in Colab).

A predictions file is JSONL. The first line is a header (`label`, plus anything
that traces the file to a training run); every other line is one answer:
`prompt_sha256` (the user prompt the model was shown), `raw_reply` (its text,
parsed like any provider's reply) and optional token counts.

`FilePredictionProvider` looks the reply up by prompt hash, so the normal ask path
(parse, guard, run, compare) scores it unchanged. The file is untrusted model
output. It holds no gold SQL and no rows. A model in a file cannot repair a
failed query: a repair prompt replays the same reply, so the first answer decides."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from ask import prompt
from common.llm import LLMRequest, LLMResponse
from common.llm.base import LLMBadResponseError, LLMProvider

PROVIDER_NAME = "file"
MAX_FILE_BYTES = 50 * 1024 * 1024
REPAIR_MARKER = "\n\nYour previous query failed."


class PredictionsError(Exception):
    """The file is unusable; nothing was scored."""


def prompt_hash(user_prompt: str) -> str:
    return hashlib.sha256(user_prompt.encode()).hexdigest()


@dataclass(frozen=True)
class Prediction:
    raw_reply: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class PredictionsFile:
    label: str
    header: dict
    sha256: str
    answers: dict[str, Prediction]


def load(path: Path) -> PredictionsFile:
    if not path.exists():
        raise PredictionsError(f"Predictions file not found: {path}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise PredictionsError("Predictions file is too large.")
    data = path.read_bytes()
    lines = [line for line in data.decode().splitlines() if line.strip()]
    try:
        header = json.loads(lines[0])["header"]
        label = header["label"]
    except (IndexError, KeyError, TypeError, ValueError):
        raise PredictionsError(
            'The first line must be {"header": {"label": ...}}.'
        ) from None
    if not isinstance(label, str) or not label.strip() or len(label) > 100:
        raise PredictionsError("The header label must be 1 to 100 characters.")
    answers: dict[str, Prediction] = {}
    for number, line in enumerate(lines[1:], start=2):
        try:
            row = json.loads(line)
            key, reply = row["prompt_sha256"], row["raw_reply"]
            if not isinstance(key, str) or not isinstance(reply, str):
                raise TypeError
            tokens = (int(row.get("input_tokens", 0)), int(row.get("output_tokens", 0)))
        except (KeyError, TypeError, ValueError):
            raise PredictionsError(f"Line {number} is not a valid answer.") from None
        if key in answers:
            raise PredictionsError(f"Line {number} repeats an earlier prompt.")
        answers[key] = Prediction(reply, *tokens)
    if not answers:
        raise PredictionsError("The file has no answers.")
    return PredictionsFile(
        label.strip(), header, hashlib.sha256(data).hexdigest(), answers
    )


class FilePredictionProvider(LLMProvider):
    provider = PROVIDER_NAME

    def __init__(self, file: PredictionsFile) -> None:
        self.model = file.label
        self.file = file
        self.missing = 0

    def generate(self, request: LLMRequest) -> LLMResponse:
        key = prompt_hash(request.prompt.split(REPAIR_MARKER, 1)[0])
        found = self.file.answers.get(key)
        if found is None:
            self.missing += 1
            raise LLMBadResponseError()
        return LLMResponse(
            found.raw_reply, self.model, found.input_tokens, found.output_tokens
        )

    def validate_key(self) -> None:
        return None


def user_prompt(question: str, schema_text: str) -> str:
    """What the model is shown for one question: the hash key of its answer."""
    return prompt.build_prompt(question, schema_text)
