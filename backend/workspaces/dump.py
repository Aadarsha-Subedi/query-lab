"""Read a plain-SQL `pg_dump` and decide, statement by statement, what may run.

The reader streams (a dump can be far bigger than memory on a 1 GiB container):
it takes lines, builds one statement at a time and yields an `Item`. The allowlist
here is a friendly first line, so a bad dump is refused with its statement number
and line before anything is written; the workspace role is still the real
boundary (see test_isolation.py).

- run:   CREATE TABLE / INDEX / SEQUENCE / VIEW, ALTER TABLE ... ADD / SET DEFAULT
         / SET NOT NULL, ALTER SEQUENCE ... OWNED BY, COMMENT ON, INSERT;
- copy:  COPY ... FROM STDIN, with the data lines that follow up to `\\.`;
- skip:  SET, GRANT, REVOKE, OWNER TO, SELECT setval / set_config (a dump's
         preamble and tail; they are counted by `classify` but never yielded);
- refuse: everything else, with a message that says why.

`public.` is removed from names so the objects land in the workspace schema (the
connection's search_path is only that schema). So is the name of a schema the dump
creates itself (`CREATE SCHEMA app;` is skipped, then `app.` is removed). Any other
qualifier is left alone and Postgres refuses it, because the role has no access to
another schema.
"""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Literal

from workspaces import sqltext

Kind = Literal["run", "skip", "copy"]

SKIP_WORDS = frozenset(["set", "grant", "revoke", "reset"])
# Newer pg_dump wraps its output in these (a guard for psql, harmless to skip).
PSQL_SKIPPED = frozenset(["\\restrict", "\\unrestrict"])
REFUSED = {
    "drop": "DROP is not allowed in a dump import.",
    "delete": "DELETE is not allowed in a dump import.",
    "update": "UPDATE is not allowed in a dump import.",
    "truncate": "TRUNCATE is not allowed in a dump import.",
    "do": "DO blocks are not allowed in a dump import.",
    "begin": "Leave out BEGIN and COMMIT. The import is one transaction.",
    "start": "Leave out BEGIN and COMMIT. The import is one transaction.",
    "commit": "Leave out BEGIN and COMMIT. The import is one transaction.",
    "end": "Leave out BEGIN and COMMIT. The import is one transaction.",
    "rollback": "Leave out BEGIN and COMMIT. The import is one transaction.",
}
CREATE_ALLOWED = re.compile(
    r"^create\s+(?:unique\s+)?(table|index|sequence|(?:or\s+replace\s+)?view)\b",
    re.I,
)
CREATE_REFUSED = {
    "role": "CREATE ROLE is not allowed.",
    "user": "CREATE USER is not allowed.",
    "extension": "Extensions are not allowed. Dump without them or remove them.",
    "function": "Functions are not allowed in a dump import.",
    "procedure": "Procedures are not allowed in a dump import.",
    "trigger": "Triggers are not allowed in a dump import.",
    "schema": "Schemas are not allowed. Everything goes into your workspace.",
    "type": "Custom types are not allowed. Use the built-in types.",
    "domain": "Domains are not allowed. Use the built-in types.",
    "database": "CREATE DATABASE is not allowed.",
    "policy": "Row security policies are not allowed.",
    "rule": "Rules are not allowed.",
    "publication": "Publications are not allowed.",
    "subscription": "Subscriptions are not allowed.",
    "server": "Foreign servers are not allowed.",
    "foreign": "Foreign tables are not allowed.",
    "materialized": "Materialized views are not allowed. Use a view.",
}
ALTER_ALLOWED = re.compile(
    r"^alter\s+(?:table|sequence)\s+(?:only\s+)?(?:if\s+exists\s+)?\S+\s+"
    r"(?:add\s|alter\s+column\s|owner\s+to\s|owned\s+by\s)",
    re.I,
)
ALTER_REFUSED = re.compile(
    r"\b(trigger|rule|policy|security|tablespace|inherit|of\s+type|attach|detach)\b",
    re.I,
)
COMMENT_ALLOWED = re.compile(
    r"^comment\s+on\s+(table|column|index|view|sequence|constraint)\b", re.I
)
COPY_FROM_STDIN = re.compile(r"^copy\s+.+\s+from\s+stdin\b", re.I | re.S)
TEMP_WORDS = re.compile(r"^create\s+(?:global\s+|local\s+)?(?:temp|temporary)\b", re.I)
SELECT_SKIPPED = re.compile(
    r"^select\s+(?:pg_catalog\.)?(?:setval|set_config)\s*\(", re.I
)

CREATE_SCHEMA = re.compile(
    r"""^create\s+schema\s+(?:if\s+not\s+exists\s+)?("(?:[^"]|"")+"|[A-Za-z_][A-Za-z_0-9$]*)""",
    re.I,
)
COMMENT_ON_SCHEMA = re.compile(r"^comment\s+on\s+schema\b", re.I)


@lru_cache(maxsize=32)
def _prefix_pattern(schemas: frozenset[str]) -> re.Pattern[str]:
    """What must be left untouched while removing `<schema>.`: strings, quoted
    names, dollar quotes and comments. Any other `<schema>.` loses the prefix."""
    names = "|".join(re.escape(name) for name in sorted(schemas, key=len, reverse=True))
    return re.compile(
        rf"""
        (?P<keep>
            (?P<regclass>'(?:[^']|'')*')(?=::regclass)
          | '(?:[^']|'')*'
          | "(?:{names})"\s*\.\s*(?P<quoted>)
          | "(?:[^"]|"")*"
          | (?P<tag>\$[A-Za-z_0-9]*\$).*?(?P=tag)
          | --[^\n]*
          | /\*.*?\*/
        )
        | \b(?:{names})\s*\.
        """,
        re.I | re.S | re.X,
    )


class DumpRefused(Exception):
    """A statement the import will not run. `number` counts from 1 across the file
    and `line` is the file line where the statement starts."""

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
    # For `copy`: the data lines (without the `\.` end). Must be read before the
    # next Item is asked for; the reader drains whatever the caller left.
    data: Iterator[str] = field(default_factory=lambda: iter(()))


def strip_schemas(text: str, schemas: Iterable[str] = ("public",)) -> str:
    """Remove `public.` and the dump's own schema names from object names, so
    everything lands in the workspace schema (the connection's search_path)."""
    names = frozenset(schemas) | {"public"}
    pattern = _prefix_pattern(names)

    def replace(match: re.Match[str]) -> str:
        if match.group("keep") is None:
            return ""  # bare `schema.`
        if match.group("quoted") is not None:
            return ""  # `"schema".`
        if match.group("regclass") is not None:  # nextval('schema.t_id_seq'::regclass)
            return re.sub(
                rf"""^'(?:"?(?:{"|".join(re.escape(n) for n in names)})"?\.)""",
                "'",
                match.group(0),
                flags=re.I,
            )
        return match.group(0)

    return pattern.sub(replace, text)


strip_public = strip_schemas


def classify(statement: str, number: int, line: int) -> Kind:
    """`run`, `skip` or `copy` for the statement, or DumpRefused with a reason."""
    text = re.sub(r"--[^\n]*|/\*.*?\*/", " ", statement, flags=re.S).strip()
    word = sqltext.first_word(text)
    if word in SKIP_WORDS:
        return "skip"
    if word in REFUSED:
        raise DumpRefused(number, line, REFUSED[word])
    if word == "select":
        if SELECT_SKIPPED.match(text):
            return "skip"
        raise DumpRefused(
            number, line, "Only setval and set_config SELECTs are skipped."
        )
    if word == "insert":
        return "run"
    if word == "copy":
        if COPY_FROM_STDIN.match(text):
            return "copy"
        raise DumpRefused(
            number, line, "Only COPY ... FROM STDIN is allowed (no files, no PROGRAM)."
        )
    if word == "comment":
        if COMMENT_ALLOWED.match(text):
            return "run"
        raise DumpRefused(
            number,
            line,
            "Only comments on tables, columns, indexes, views, sequences and constraints.",
        )
    if word == "alter":
        if re.search(r"\bowner\s+to\b", text, re.I):
            return "skip"
        if ALTER_REFUSED.search(text) or not ALTER_ALLOWED.match(text):
            raise DumpRefused(
                number,
                line,
                "This ALTER is not allowed. Only ADD, ALTER COLUMN and OWNED BY on tables and sequences.",
            )
        return "run"
    if word == "create":
        if TEMP_WORDS.match(text):
            raise DumpRefused(number, line, "Temporary tables are not allowed.")
        if CREATE_ALLOWED.match(text):
            return "run"
        target = re.sub(r"^create\s+(?:or\s+replace\s+)?", "", text, flags=re.I)
        noun = sqltext.first_word(target)
        raise DumpRefused(
            number,
            line,
            CREATE_REFUSED.get(noun, f"CREATE {noun.upper()} is not allowed."),
        )
    raise DumpRefused(number, line, f"{word.upper()} is not allowed in a dump import.")


def read(lines: Iterable[str]) -> Iterator[Item]:
    """Statements of a dump, one at a time, each already classified. Raises
    DumpRefused at the first statement that may not run, before yielding it."""
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
            command = raw.strip()
            if command.startswith("\\"):  # a psql meta-command, not SQL
                word = command.split(None, 1)[0]
                if word in PSQL_SKIPPED:
                    continue
                raise DumpRefused(
                    number + 1,
                    line_no,
                    f"{word} is a psql command, not SQL. Dump with plain pg_dump output only.",
                )
        buffer += raw if raw.endswith("\n") else raw + "\n"
        statements, rest = sqltext.split_partial(buffer)
        for text in statements:
            text = text.strip()
            if not sqltext.first_word(text):
                continue
            number += 1
            plain = re.sub(r"--[^\n]*|/\*.*?\*/", " ", text, flags=re.S).strip()
            created = CREATE_SCHEMA.match(plain)
            if created:  # the dump's own schema: its objects go into the workspace
                name = created.group(1)
                schemas.add(
                    name[1:-1].replace('""', '"') if name[0] == '"' else name.lower()
                )
                continue
            if COMMENT_ON_SCHEMA.match(plain):
                continue
            kind = classify(text, number, buffer_line)
            item = Item(
                kind=kind,
                text=strip_schemas(text, schemas),
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
