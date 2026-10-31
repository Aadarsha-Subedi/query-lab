"""Names a user types become safe names here, once, before anything uses them.

Workspace names are display text (stored as data, never an identifier). Table and
column names become identifiers: lower-case ASCII slugs that cannot start with a
digit, cannot be a reserved word or a catalog name, and fit Postgres's 63-byte
limit. Even so, they are only ever passed through `psycopg.sql.Identifier`, never
joined into SQL text.
"""

import re
import unicodedata
from collections.abc import Iterable

from django.conf import settings

from workspaces.errors import InvalidName

# Postgres truncates identifiers beyond this (NAMEDATALEN - 1); a fact, not a tunable.
PG_IDENTIFIER_MAX = 63

# The hidden primary key every user table gets (5.5.1).
ROW_ID = "_row_id"

# Allowed column types: the API name and the Postgres type it maps to.
COLUMN_TYPES: dict[str, str] = {
    "text": "text",
    "integer": "integer",
    "bigint": "bigint",
    "numeric": "numeric",
    "boolean": "boolean",
    "date": "date",
    "timestamp": "timestamp without time zone",
}

# Words PostgreSQL reserves (SQL keywords that cannot be a bare name), plus
# names we keep for ourselves.
RESERVED_WORDS = frozenset(
    [
        "all",
        "analyse",
        "analyze",
        "and",
        "any",
        "array",
        "as",
        "asc",
        "asymmetric",
        "authorization",
        "binary",
        "both",
        "case",
        "cast",
        "check",
        "collate",
        "collation",
        "column",
        "concurrently",
        "constraint",
        "create",
        "cross",
        "current_catalog",
        "current_date",
        "current_role",
        "current_schema",
        "current_time",
        "current_timestamp",
        "current_user",
        "default",
        "deferrable",
        "desc",
        "distinct",
        "do",
        "else",
        "end",
        "except",
        "false",
        "fetch",
        "for",
        "foreign",
        "freeze",
        "from",
        "full",
        "grant",
        "group",
        "having",
        "ilike",
        "in",
        "initially",
        "inner",
        "intersect",
        "into",
        "is",
        "isnull",
        "join",
        "lateral",
        "leading",
        "left",
        "like",
        "limit",
        "localtime",
        "localtimestamp",
        "natural",
        "not",
        "notnull",
        "null",
        "offset",
        "on",
        "only",
        "or",
        "order",
        "outer",
        "overlaps",
        "placing",
        "primary",
        "references",
        "returning",
        "right",
        "select",
        "session_user",
        "similar",
        "some",
        "symmetric",
        "system_user",
        "table",
        "tablesample",
        "then",
        "to",
        "trailing",
        "true",
        "union",
        "unique",
        "user",
        "using",
        "variadic",
        "verbose",
        "when",
        "where",
        "window",
        "with",
        "public",
        "demo",
        "information_schema",
        "querylab",
        "querylab_app",
        "querylab_reader",
    ]
)

CATALOG_PREFIXES = ("pg_", "sql_", "ws_")


def _ascii_slug(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", folded.lower()).strip("_")
    return slug


def identifier_slug(
    text: str, *, kind: str, max_length: int = PG_IDENTIFIER_MAX
) -> str:
    """A safe identifier from free text. `kind` is "table" or "column" and only
    picks the fallback and the prefix used when the text has no usable start."""
    slug = _ascii_slug(text)
    if not slug:
        slug = f"unnamed_{kind}"
    if slug[0].isdigit() or slug.startswith(CATALOG_PREFIXES):
        slug = f"{kind[0]}_{slug}"
    if slug in RESERVED_WORDS:
        slug = f"{slug}_{kind}"
    return slug[:max_length].rstrip("_") or f"unnamed_{kind}"


def unique(
    name: str, taken: Iterable[str], *, max_length: int = PG_IDENTIFIER_MAX
) -> str:
    """`name`, or `name_2`, `name_3`, ... when it is already taken (the suffix
    never pushes it past `max_length`)."""
    used = set(taken)
    if name not in used:
        return name
    counter = 2
    while True:
        suffix = f"_{counter}"
        candidate = f"{name[: max_length - len(suffix)]}{suffix}"
        if candidate not in used:
            return candidate
        counter += 1


def table_name(text: str, taken: Iterable[str] = ()) -> str:
    return unique(identifier_slug(text, kind="table"), taken)


def column_name(text: str, taken: Iterable[str] = ()) -> str:
    return unique(identifier_slug(text, kind="column"), [ROW_ID, *taken])


def column_names(texts: Iterable[str]) -> list[str]:
    """Slugs for a list of headers, in order, de-duplicated (empty headers become
    `column`, `column_2`, ...)."""
    names: list[str] = []
    for text in texts:
        names.append(column_name(text, names))
    return names


def workspace_name(text: str) -> str:
    """The display name: trimmed, one space between words, no control characters."""
    cleaned = " ".join(
        "".join(ch for ch in text if ch.isprintable() or ch.isspace()).split()
    )
    if not cleaned:
        raise InvalidName("A workspace needs a name.")
    if len(cleaned) > settings.WORKSPACE_NAME_MAX_LENGTH:
        raise InvalidName(
            f"A workspace name has at most {settings.WORKSPACE_NAME_MAX_LENGTH} characters."
        )
    return cleaned


def column_type(name: str) -> str:
    """The Postgres type for an API type name, or InvalidName."""
    try:
        return COLUMN_TYPES[name]
    except KeyError:
        allowed = ", ".join(COLUMN_TYPES)
        raise InvalidName(f"Unknown column type. Allowed: {allowed}.") from None
