"""Guessing what a CSV file is, from its first bytes: text or not, the encoding,
the delimiter, whether the first row is a header, the column names and a type for
each column. Only a sample is read here; the import job checks every row again."""

import codecs
import csv
import io
from dataclasses import dataclass, field

from django.conf import settings

from workspaces import naming, values
from workspaces.errors import (
    ImportEmpty,
    ImportEncoding,
    ImportNotText,
    ImportTooManyColumns,
)

DELIMITERS = [",", ";", "\t", "|"]
BOOLEAN_WORDS = {"true", "false", "yes", "no", "t", "f"}
# Records looked at to pick the delimiter.
DELIMITER_RECORDS = 20
UTF16_BOMS = (codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)


@dataclass
class Sniffed:
    delimiter: str
    has_header: bool
    headers: list[str]
    names: list[str]
    types: list[str]
    sample_rows: list[list[str]] = field(default_factory=list)

    @property
    def column_count(self) -> int:
        return len(self.names)


class TypeGuess:
    """Tracks which types every non-empty value of one column could still be.
    `result()` is the narrowest type that fits all of them, `text` otherwise."""

    def __init__(self) -> None:
        self.seen = False
        self.boolean = self.int32 = self.int64 = True
        self.numeric = self.date = self.timestamp = True

    def add(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.seen = True
        if self.boolean and text.lower() not in BOOLEAN_WORDS:
            self.boolean = False
        # "007" and "+1" are identifiers and phone numbers, not numbers.
        zero_led = len(text) > 1 and text[0] == "0" and text[1].isdigit()
        for name, api in (
            ("int32", "integer"),
            ("int64", "bigint"),
            ("numeric", "numeric"),
        ):
            if getattr(self, name):
                ok = not zero_led and not text.startswith("+") and _fits(text, api)
                setattr(self, name, ok)
        if self.date:
            self.date = _fits(text, "date")
        if self.timestamp:
            self.timestamp = _fits(text, "timestamp")

    def result(self) -> str:
        if not self.seen:
            return "text"
        for flag, api in (
            (self.boolean, "boolean"),
            (self.int32, "integer"),
            (self.int64, "bigint"),
            (self.numeric, "numeric"),
            (self.date, "date"),
            (self.timestamp, "timestamp"),
        ):
            if flag:
                return api
        return "text"


def _fits(text: str, api_type: str) -> bool:
    try:
        values.coerce(text, api_type)
    except values.BadValue:
        return False
    return True


def decode_sample(sample: bytes) -> str:
    """The sample as text, or a typed error. A cut-off last character is fine."""
    if not sample.strip():
        raise ImportEmpty()
    if sample.startswith(UTF16_BOMS):
        raise ImportEncoding()
    if b"\x00" in sample:
        raise ImportNotText()
    decoder = codecs.getincrementaldecoder("utf-8-sig")()
    try:
        text = decoder.decode(sample, final=False)
    except UnicodeDecodeError:
        raise ImportEncoding() from None
    control = sum(1 for ch in text if ord(ch) < 32 and ch not in "\r\n\t\f")
    if text and control / len(text) > 0.05:
        raise ImportNotText()
    if not text.strip():
        raise ImportEmpty()
    return text


def _records(text: str, delimiter: str, limit: int) -> list[list[str]]:
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    rows: list[list[str]] = []
    try:
        for row in reader:
            rows.append(row)
            if len(rows) > limit:
                break
    except csv.Error:
        pass  # a cut-off quoted field at the end of the sample
    return rows


def detect_delimiter(text: str) -> str:
    best, best_score = ",", (0.0, 0)
    for delimiter in DELIMITERS:
        rows = _records(text, delimiter, DELIMITER_RECORDS)[:-1] or _records(
            text, delimiter, DELIMITER_RECORDS
        )
        counts = [len(r) for r in rows if r]
        if not counts:
            continue
        modal = max(set(counts), key=counts.count)
        if modal < 2:
            continue
        score = (counts.count(modal) / len(counts), modal)
        if score > best_score:
            best, best_score = delimiter, score
    return best


def looks_like_header(first: list[str], second: list[str] | None) -> bool:
    """Header unless every cell of the first row is a number or a date."""
    cells = [c.strip() for c in first if c.strip()]
    if not cells:
        return True
    return not all(
        _fits(c, "numeric") or _fits(c, "date") or _fits(c, "timestamp") for c in cells
    )


def sniff(
    sample: bytes,
    *,
    delimiter: str | None = None,
    has_header: bool | None = None,
) -> Sniffed:
    text = decode_sample(sample)
    delimiter = delimiter or detect_delimiter(text)
    rows = _records(text, delimiter, settings.IMPORT_SNIFF_ROWS + 1)
    # The last record may be cut off by the end of the sample.
    if len(sample) >= settings.IMPORT_SNIFF_BYTES and len(rows) > 1:
        rows = rows[:-1]
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise ImportEmpty()
    first = rows[0]
    if has_header is None:
        has_header = looks_like_header(first, rows[1] if len(rows) > 1 else None)
    width = max(len(r) for r in rows[: settings.IMPORT_SNIFF_ROWS + 1])
    if width > settings.IMPORT_MAX_COLUMNS:
        raise ImportTooManyColumns()
    headers = (
        [*first, *[""] * (width - len(first))]
        if has_header
        else [f"column_{i}" for i in range(1, width + 1)]
    )
    data = rows[1:] if has_header else rows
    guesses = [TypeGuess() for _ in range(width)]
    for row in data[: settings.IMPORT_SNIFF_ROWS]:
        for i, cell in enumerate(row[:width]):
            guesses[i].add(cell)
    return Sniffed(
        delimiter=delimiter,
        has_header=has_header,
        headers=headers,
        names=naming.column_names(headers),
        types=[g.result() for g in guesses],
        sample_rows=[
            [*r, *[""] * (width - len(r))][:width]
            for r in data[: settings.IMPORT_PREVIEW_ROWS]
        ],
    )
