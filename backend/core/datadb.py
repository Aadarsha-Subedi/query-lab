"""SQL for the data database (querylab): rendering infra/sql files with values
from settings and applying them as the owner role.

Placeholders in the files (in braces) are filled with psycopg's sql module,
so identifiers are quoted and literals escaped, never string-formatted:

    schema            the demo schema (identifier)
    reader_role       the reader login role (identifier)
    reader_role_name  the same name as a string literal
    reader_password   its password (literal)
    statement_timeout READER_STATEMENT_TIMEOUT_MS (literal)
    data_db, app_db   database names (identifiers)
"""

from pathlib import Path

from django.conf import settings
from django.db import connections
from psycopg import sql

DEMO_SCHEMA = "demo"


def sql_files() -> list[Path]:
    """Every file in DATA_SQL_DIR (infra/sql), in the order of their numeric prefixes."""
    return sorted(Path(settings.DATA_SQL_DIR).glob("*.sql"))


def placeholders(schema: str = DEMO_SCHEMA) -> dict[str, sql.Composable]:
    databases = settings.DATABASES
    reader = databases[settings.DATA_READER_DB_ALIAS]
    return {
        "schema": sql.Identifier(schema),
        "reader_role": sql.Identifier(reader["USER"]),
        "reader_role_name": sql.Literal(reader["USER"]),
        "reader_password": sql.Literal(reader["PASSWORD"]),
        "statement_timeout": sql.Literal(settings.READER_STATEMENT_TIMEOUT_MS),
        "data_db": sql.Identifier(databases[settings.DATA_DB_ALIAS]["NAME"]),
        "app_db": sql.Identifier(databases["default"]["NAME"]),
    }


def render(path: Path, values: dict[str, sql.Composable]) -> sql.Composed:
    return sql.SQL(path.read_text()).format(**values)


def apply(paths: list[Path], values: dict[str, sql.Composable]) -> None:
    """Run each file as the owner role, all in one transaction."""
    connection = connections[settings.DATA_DB_ALIAS]
    connection.ensure_connection()
    raw = connection.connection
    with raw.transaction(), raw.cursor() as cursor:
        for path in paths:
            cursor.execute(render(path, values))
