"""Read a plain-SQL `pg_dump` and prepare it to run in a workspace.

The reader streams (a dump can be far bigger than memory on a 1 GiB container): it
takes lines, builds one statement at a time and yields an `Item`. It does not judge
what a dump may do: every statement runs as the workspace's own `_rw` role, and that
role is the boundary (see test_isolation.py). What Postgres refuses is reported with
its statement number and line.

The reader only sets aside what belongs to the source server, or would break the
copy, and could never work here:

- preamble and server-level statements: SET, GRANT, REVOKE, OWNER TO, roles,
  databases, extensions, publications, tablespaces, psql `\\` commands;
- transaction control: the import is one transaction, and a COMMIT inside the dump
  would end it before the size check;
- DROP (`pg_dump --clean`): the workspace is empty, or was just cleared;
- row security and policies: they name roles that do not exist here, and would hide
  the rows from the role that reads them. This is a private copy for analysis.

`public.` and the name of any schema the dump creates are removed from object names
(also in function bodies, `::regclass` casts and `setval`), so everything lands in
the workspace schema. Any other qualifier is left alone and Postgres refuses it.
"""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from workspaces import sqltext

Kind = Literal["run", "skip", "copy"]

SKIPPED = re.compile(
    r"""^(?:
        set | reset | grant | revoke | drop | vacuum | security \s+ label
      | begin | start \s+ transaction | commit | end | rollback | abort
      | alter \s+ default \s+ privileges
      | select \s+ (?:pg_catalog \. )? set_config \s* \(
      | (?:create | alter | comment \s+ on) \s+ (?:
            extension | schema | role | user | group | database | policy
          | publication | subscription | tablespace | event \s+ trigger
        ) \b
    )""",
    re.I | re.X,
)
OWNER_TO = re.compile(r"\bowner\s+to\b", re.I)
ALTER_SKIPPED = re.compile(
    r"^alter\s+table\b.*\b(?:row\s+level\s+security|drop\s+constraint)\b", re.I | re.S
)
COPY_FROM_STDIN = re.compile(r"^copy\s+.+\s+from\s+stdin\b", re.I | re.S)
CREATE_SCHEMA = re.compile(
    r"""^create\s+schema\s+(?:if\s+not\s+exists\s+)?("(?:[^"]|"")+"|[A-Za-z_][A-Za-z_0-9$]*)""",
    re.I,
)
CREATE_ROUTINE = re.compile(
    r"^create\s+(?:or\s+replace\s+)?(?:function|procedure)\b", re.I
)
ROUTINE_SEARCH_PATH = re.compile(
    r"^\s*SET\s+search_path\s+(?:TO|=)\s+.*\n", re.I | re.M
)


@lru_cache(maxsize=32)
def _prefix_pattern(schemas: frozenset[str]) -> re.Pattern[str]:
    """What must be left untouched while removing `<schema>.`: strings, other quoted
    names and comments. Any other `<schema>.` loses the prefix. A string that names
    an object (a regclass cast, setval) and a dollar-quoted body are rewritten too."""
    names = "|".join(re.escape(name) for name in sorted(schemas, key=len, reverse=True))
    return re.compile(
        rf"""
        (?P<keep>
            (?P<named>(?<=setval\()'(?:[^']|'')*'|'(?:[^']|'')*'(?=::regclass))
          | '(?:[^']|'')*'
          | "(?:{names})"\s*\.\s*(?P<quoted>)
          | "(?:[^"]|"")*"
          | (?P<tag>\$[A-Za-z_0-9]*\$)(?P<body>.*?)(?P=tag)
          | --[^\n]*
          | /\*.*?\*/
        )
        | \b(?:{names})\s*\.
        """,
        re.I | re.S | re.X,
    )


class DumpRefused(Exception):
    """The dump cannot be read (it ends in the middle of a statement). `number` counts
    from 1 across the file and `line` is the file line where the statement starts."""

    def __init__(self, number: int, line: int, message: str):
        super().__init__(message)
        self.number = number
        self.line = line
        self.message = message


@dataclass
class Item:
    kind: Kind
    text: str
    number: int
    line: int
    # For `copy`: the data lines (without the `\\.` end). Must be read before the
    # next Item is asked for; the reader drains whatever the caller left.
    data: Iterator[str] = field(default_factory=lambda: iter(()))


def strip_schemas(text: str, schemas: Iterable[str] = ("public",)) -> str:
    """Remove `public.` and the dump's own schema names from object names, so
    everything lands in the workspace schema (the connection's search_path)."""
    names = frozenset(schemas) | {"public"}
    pattern = _prefix_pattern(names)
    in_string = re.compile(
        rf"""^'(?:"?(?:{"|".join(re.escape(n) for n in names)})"?\.)""", re.I
    )

    def replace(match: re.Match[str]) -> str:
        if match.group("keep") is None or match.group("quoted") is not None:
            return ""  # `schema.` or `"schema".`
        if match.group("named") is not None:
            return in_string.sub("'", match.group(0))
        if match.group("tag") is not None:
            tag = match.group("tag")
            return f"{tag}{strip_schemas(match.group('body'), names)}{tag}"
        return match.group(0)

    return pattern.sub(replace, text)


def _plain(statement: str) -> str:
    return re.sub(r"--[^\n]*|/\*.*?\*/", " ", statement, flags=re.S).strip()


def classify(statement: str) -> Kind:
    """`copy` for COPY ... FROM STDIN, `skip` for what is set aside (module docstring),
    `run` for everything else."""
    text = _plain(statement)
    if SKIPPED.match(text) or OWNER_TO.search(text) or ALTER_SKIPPED.match(text):
        return "skip"
    return "copy" if COPY_FROM_STDIN.match(text) else "run"


def _prepare(text: str, schemas: Iterable[str]) -> str:
    """The statement as it runs here. A routine's own `SET search_path` would point it
    away from the workspace schema, so it goes."""
    if CREATE_ROUTINE.match(_plain(text)):
        header, dollar, rest = text.partition("$")
        text = ROUTINE_SEARCH_PATH.sub("", header) + dollar + rest
    return strip_schemas(text, schemas)


def read(lines: Iterable[str]) -> Iterator[Item]:
    """The statements to run, one at a time. Raises DumpRefused if the dump ends in
    the middle of a statement."""
    source = iter(lines)
    schemas = {"public"}
    buffer = ""
    buffer_line = 1
    line_no = 0
    number = 0
    for raw in source:
        line_no += 1
        if not sqltext.first_word(buffer):  # blank or only comments so far
            buffer, buffer_line = "", line_no
            if raw.lstrip().startswith("\\"):  # a psql meta-command, not SQL
                continue
        buffer += raw if raw.endswith("\n") else raw + "\n"
        statements, rest = sqltext.split_partial(buffer)
        for text in statements:
            text = text.strip()
            if not sqltext.first_word(text):
                continue
            number += 1
            created = CREATE_SCHEMA.match(_plain(text))
            if created:  # the dump's own schema: its objects go into the workspace
                name = created.group(1)
                schemas.add(
                    name[1:-1].replace('""', '"') if name[0] == '"' else name.lower()
                )
                continue
            kind = classify(text)
            item = Item(
                kind=kind,
                text=_prepare(text, schemas),
                number=number,
                line=buffer_line,
            )
            if kind == "copy":

                def data() -> Iterator[str]:
                    nonlocal line_no
                    for data_line in source:
                        line_no += 1
                        if data_line.rstrip("\r\n") == "\\.":
                            return
                        yield data_line

                item.data = data()
                yield item
                for _ in item.data:  # drain what the caller did not read
                    pass
            elif kind == "run":
                yield item
        # Whatever follows the last `;` stays in the buffer for the next line.
        buffer = rest
        if statements:
            buffer_line = line_no if rest.strip() else line_no + 1
    leftover = buffer.strip()
    if sqltext.first_word(leftover):
        raise DumpRefused(
            number + 1, buffer_line, "The dump ends in the middle of a statement."
        )
