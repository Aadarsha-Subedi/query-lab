"""The sqlglot guard: the model's SQL is untrusted until it passes here.

It parses the SQL as PostgreSQL and checks the syntax tree (never the text), then
returns the SQL that will actually run, rewritten from that same tree. It is the
second layer: the reader role (read-only, SELECT on `demo` only, statement
timeout) is the wall that still holds if this layer has a bug.
"""

from dataclasses import dataclass

import sqlglot
from django.conf import settings
from sqlglot import exp
from sqlglot.errors import OptimizeError, SqlglotError
from sqlglot.optimizer.qualify import qualify

from ask.errors import GuardRejected
from ask.schema import Schema
from core.datadb import DEMO_SCHEMA

DIALECT = "postgres"

# Anything that writes, changes structure, runs a command or locks rows.
FORBIDDEN_NODES: tuple[type[exp.Expr], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
    exp.Copy,
    exp.Set,
    exp.Use,
    exp.Into,
    exp.Lock,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Grant,
    exp.Analyze,
    exp.Describe,
    exp.Pragma,
)

BLOCKED_FUNCTION_PREFIXES = ("pg_", "lo_")


@dataclass(frozen=True)
class GuardReport:
    """What the guard had to change. `clean` means nothing but a missing LIMIT."""

    rewrites: tuple[str, ...] = ()

    @property
    def clean(self) -> bool:
        return not self.rewrites


@dataclass(frozen=True)
class GuardResult:
    sql: str
    report: GuardReport


def _reject(detail: str) -> GuardRejected:
    return GuardRejected(detail)


def _function_name(node: exp.Func) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.name).lower()
    return node.sql_name().lower()


def _parse(sql: str) -> exp.Expr:
    try:
        statements = [s for s in sqlglot.parse(sql, read=DIALECT) if s is not None]
    except SqlglotError:
        raise _reject("The query is not valid PostgreSQL.") from None
    if not statements:
        raise _reject("The query is empty.")
    if len(statements) > 1:
        raise _reject("Only one statement is allowed.")
    return statements[0]


def _check_kind(tree: exp.Expr) -> None:
    if not isinstance(tree, exp.Select | exp.SetOperation):
        raise _reject("Only SELECT queries are allowed.")
    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise _reject("Only read-only SELECT queries are allowed.")


def _check_functions(tree: exp.Expr) -> None:
    denied = set(settings.ASK_DENIED_FUNCTIONS)
    for node in tree.find_all(exp.Func):
        name = _function_name(node)
        if name in denied or name.startswith(BLOCKED_FUNCTION_PREFIXES):
            raise _reject(f"The function {name} is not allowed.")


def _identifier(node: exp.Expr | None) -> str:
    """An identifier as Postgres reads it: unquoted names fold to lower case,
    quoted names are exact (so "Orders" is not orders)."""
    if node is None:
        return ""
    name = str(node.name)
    return name if node.args.get("quoted") else name.lower()


def _check_tables(tree: exp.Expr, schema: Schema) -> list[str]:
    """Every table must be a known table in the schema (or a CTE). Unqualified
    names get the schema added. Returns the rewrites made."""
    ctes = {str(cte.alias).lower() for cte in tree.find_all(exp.CTE)}
    qualified = False
    for table in tree.find_all(exp.Table):
        if isinstance(table.this, exp.Func):
            continue  # a set-returning function in FROM; the function check covers it
        name = _identifier(table.this)
        if table.args.get("catalog"):
            raise _reject("Cross-database references are not allowed.")
        db = _identifier(table.args.get("db"))
        if not db and name in ctes:
            continue
        if db and db != schema.name:
            raise _reject(f"The schema {db} is not available.")
        if schema.table(name) is None:
            raise _reject(f"The table {name} does not exist.")
        if not db:
            table.set("db", exp.to_identifier(schema.name))
            qualified = True
    return ["qualified_tables"] if qualified else []


def _mapping(schema: Schema) -> dict[str, dict[str, dict[str, str]]]:
    return {
        schema.name: {
            table.name: {column.name: column.type for column in table.columns}
            for table in schema.tables
        }
    }


def _check_columns(tree: exp.Expr, schema: Schema) -> exp.Expr:
    mapping: dict[str, object] = dict(_mapping(schema))
    try:
        qualified = qualify(
            tree,
            schema=mapping,
            dialect=DIALECT,
            validate_qualify_columns=True,
            expand_stars=False,
            quote_identifiers=False,
            identify=False,
        )
        assert isinstance(qualified, exp.Expr)
        return qualified
    except OptimizeError as error:
        message = str(error).splitlines()[0] if str(error) else "Unknown column."
        raise _reject(message) from None
    except SqlglotError:
        raise _reject("The query could not be checked against the schema.") from None


def _limit_value(limit: exp.Expr | None) -> int | None:
    if limit is None:
        return None
    value = limit.args.get("expression")
    if isinstance(value, exp.Literal) and value.is_int:
        return int(value.this)
    return -1  # present but not a plain number


def _force_limit(tree: exp.Expr) -> list[str]:
    cap = settings.ASK_MAX_ROWS
    current = _limit_value(tree.args.get("limit"))
    if current is None:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(cap)))
        return []
    if current < 0 or current > cap:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(cap)))
        return ["limit_clamped"]
    return []


def check(sql: str, schema: Schema) -> GuardResult:
    """Validate and normalise `sql`, or raise GuardRejected."""
    tree = _parse(sql)
    _check_kind(tree)
    _check_functions(tree)
    rewrites = _check_tables(tree, schema)
    tree = _check_columns(tree, schema)
    rewrites += _force_limit(tree)
    return GuardResult(
        sql=tree.sql(dialect=DIALECT, comments=False),
        report=GuardReport(tuple(rewrites)),
    )


__all__ = ["DEMO_SCHEMA", "GuardReport", "GuardResult", "check"]
