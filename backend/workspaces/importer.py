"""Run a dump import: the one place a workspace is written to.

Everything happens in ONE transaction on the workspace's own `_rw` login, so a
dump either lands completely or leaves the workspace as it was (with `replace`,
the old tables are dropped inside that same transaction). The dump is read from
R2 as a stream (see `dump.py`) and every statement runs as that role: it is the
boundary, so a dump may do anything inside its own schema and nothing outside it.
The only limits are the ones that protect the container and the database: the
workspace and user size (checked as it loads and before the commit), the unzipped
size and the total time. Nothing here connects as the platform owner.

The job's result is stored on its `ImportJob` row (code, message, statement
number and file line), which is what the API and the screen show.
"""

import logging
import time
from dataclasses import dataclass

import psycopg
from django.conf import settings
from django.db.models import F
from psycopg import errors as pg_errors
from psycopg import sql

from workspaces import (
    connections,
    ddl_log,
    dump,
    quota,
    schema_version,
    storage,
)
from workspaces.errors import (
    DumpTooLarge,
    DumpUploadMissing,
    UserStorageFull,
    WorkspaceFull,
)
from workspaces.models import ImportJob, Workspace
from workspaces.sql import _scrub

logger = logging.getLogger(__name__)

# Error codes stored on a failed ImportJob (documented in API_ERRORS.md).
CODE_REFUSED = "dump_refused"
CODE_FAILED = "dump_failed"
CODE_TIMEOUT = "dump_timeout"
CODE_ENCODING = "dump_encoding"
CODE_INTERRUPTED = "dump_interrupted"
CODE_REPLACED = "dump_replaced"
CODE_NOT_EMPTY = "workspace_not_empty"
CODE_NOT_READY = "workspace_not_ready"

# A running job that has not been touched for this long is taken for dead (the
# worker was killed) and shown as failed when someone looks at it.
STALE_AFTER_SECONDS = 30 * 60
# Check the size every this many statements, and after each COPY, so a dump that
# is far over the cap stops early instead of at the end.
SIZE_CHECK_EVERY = 500

TABLES_SQL = """
SELECT c.relname, c.relkind FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relkind IN ('r', 'p', 'f', 'm', 'v', 'S')
-- Tables first: a sequence a table owns goes with it, and cannot be dropped alone.
ORDER BY array_position(ARRAY['r', 'p', 'f', 'm', 'v', 'S']::"char"[], c.relkind)
"""
ROUTINES_SQL = """
SELECT p.oid::regprocedure::text FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = %s
"""
TYPES_SQL = """
SELECT t.typname, t.typtype FROM pg_type t
JOIN pg_namespace n ON n.oid = t.typnamespace
LEFT JOIN pg_class c ON c.oid = t.typrelid
WHERE n.nspname = %s
  AND (t.typtype IN ('e', 'd', 'r') OR (t.typtype = 'c' AND c.relkind = 'c'))
"""
TABLE_COUNT_SQL = """
SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = %s AND c.relkind IN ('r', 'p')
"""


@dataclass
class Failure(Exception):
    code: str
    message: str
    statement: int | None = None
    line: int | None = None


def _set_limits(connection: psycopg.Connection) -> None:
    """The role's own timeouts are short (a console request); an import may run
    longer, and may sit between statements while R2 delivers the next chunk."""
    value = str(settings.DUMP_STATEMENT_TIMEOUT_MS)
    for name in ("statement_timeout", "idle_in_transaction_session_timeout"):
        connection.execute("SELECT set_config(%s, %s, true)", [name, value])
    # As pg_dump itself asks: a routine may refer to something created after it.
    connection.execute("SELECT set_config('check_function_bodies', 'off', true)")


def _existing_objects(
    connection: psycopg.Connection, schema_name: str
) -> list[tuple[str, str]]:
    return [
        (str(name), str(kind))
        for name, kind in connection.execute(TABLES_SQL, [schema_name]).fetchall()
    ]


def _is_empty(connection: psycopg.Connection, schema_name: str) -> bool:
    return not (
        _existing_objects(connection, schema_name)
        or connection.execute(ROUTINES_SQL, [schema_name]).fetchone()
        or connection.execute(TYPES_SQL, [schema_name]).fetchone()
    )


def _clear(connection: psycopg.Connection, schema_name: str) -> None:
    """Drop everything in the workspace schema (replace mode). The role cannot make
    a new schema, so the objects go one by one; CASCADE takes what depends on them."""
    nouns = {
        "v": "VIEW",
        "m": "MATERIALIZED VIEW",
        "S": "SEQUENCE",
        "f": "FOREIGN TABLE",
    }
    for name, kind in _existing_objects(connection, schema_name):
        connection.execute(
            sql.SQL("DROP {} IF EXISTS {}.{} CASCADE").format(
                sql.SQL(nouns.get(kind, "TABLE")),
                sql.Identifier(schema_name),
                sql.Identifier(name),
            )
        )
    for (routine,) in connection.execute(ROUTINES_SQL, [schema_name]).fetchall():
        # regprocedure text comes from Postgres, already quoted.
        connection.execute(
            sql.SQL("DROP ROUTINE IF EXISTS {} CASCADE").format(sql.SQL(routine))
        )
    for name, kind in connection.execute(TYPES_SQL, [schema_name]).fetchall():
        connection.execute(
            sql.SQL("DROP {} IF EXISTS {}.{} CASCADE").format(
                sql.SQL("DOMAIN" if kind == "d" else "TYPE"),
                sql.Identifier(schema_name),
                sql.Identifier(name),
            )
        )


def _check_size(
    connection: psycopg.Connection, workspace: Workspace, *, final: bool
) -> None:
    size = quota.measure(connection, workspace.schema_name)
    if size > settings.WORKSPACE_MAX_BYTES:
        raise WorkspaceFull()
    if final:
        quota.ensure_within(connection, workspace)


def _table_count(connection: psycopg.Connection, schema_name: str) -> int:
    row = connection.execute(TABLE_COUNT_SQL, [schema_name]).fetchone()
    return int(row[0]) if row else 0


def _execute(
    connection: psycopg.Connection, item: dump.Item, workspace: Workspace
) -> None:
    try:
        if item.kind == "copy":
            with connection.cursor() as cursor, cursor.copy(item.text) as copy:
                for line in item.data:
                    copy.write(line)
        else:
            connection.execute(item.text)
    except pg_errors.QueryCanceled:
        raise Failure(
            CODE_TIMEOUT,
            "The import took too long and was stopped. Nothing was changed.",
            item.number,
            item.line,
        ) from None
    except psycopg.Error as error:
        code = error.sqlstate or "XX000"
        message = _scrub(
            str(error).splitlines()[0] if str(error) else "error",
            workspace.schema_name,
        )
        raise Failure(
            CODE_FAILED, f"{code}: {message}", item.number, item.line
        ) from None


def _load(job: ImportJob, workspace: Workspace) -> tuple[int, int]:
    """The transaction. Returns (statements run, tables now in the workspace)."""
    lines = storage.read_lines(
        job.object_key, max_text_bytes=settings.DUMP_MAX_TEXT_BYTES
    )
    ran = 0
    with connections.workspace_connection(
        workspace.pk, "rw", workspace.credential_version
    ) as connection:
        _set_limits(connection)
        if job.replace:
            _clear(connection, workspace.schema_name)
        elif not _is_empty(connection, workspace.schema_name):
            raise Failure(
                CODE_NOT_EMPTY,
                "This workspace already has tables. Use Replace data.",
            )
        try:
            for item in dump.read(lines):
                ran += 1
                _execute(connection, item, workspace)
                if item.kind == "copy" or ran % SIZE_CHECK_EVERY == 0:
                    _check_size(connection, workspace, final=False)
        except dump.DumpRefused as refused:
            raise Failure(
                CODE_REFUSED, refused.message, refused.number, refused.line
            ) from None
        except UnicodeDecodeError:
            raise Failure(CODE_ENCODING, "The dump must be UTF-8 text.") from None
        tables = _table_count(connection, workspace.schema_name)
        _check_size(connection, workspace, final=True)
    return ran, tables


def _fail(job: ImportJob, failure: Failure) -> None:
    job.status = ImportJob.FAILED
    job.error_code = failure.code
    job.error_message = failure.message
    job.error_statement = failure.statement
    job.error_line = failure.line
    job.save()


def run(job_id: int) -> None:
    """The Huey task body. Never raises: the outcome is on the job row."""
    job = ImportJob.objects.select_related("workspace", "owner").get(pk=job_id)
    if job.status != ImportJob.QUEUED:
        return
    workspace = job.workspace
    job.status = ImportJob.RUNNING
    job.save(update_fields=["status", "updated_at"])
    started = time.monotonic()
    try:
        if workspace.status != Workspace.STATUS_READY:
            raise Failure(CODE_NOT_READY, "This workspace is not ready.")
        ran, tables = _load(job, workspace)
    except Failure as failure:
        _fail(job, failure)
    except WorkspaceFull as error:
        _fail(job, Failure(error.error_code, error.message))
    except UserStorageFull as error:
        _fail(job, Failure(error.error_code, error.message))
    except (DumpTooLarge, DumpUploadMissing) as error:
        _fail(job, Failure(error.error_code, error.message))
    except Exception:
        logger.exception("Import job %s crashed", job.pk)
        _fail(
            job,
            Failure(CODE_FAILED, "The import failed unexpectedly. Try again."),
        )
    else:
        job.status = ImportJob.SUCCEEDED
        job.statements_run = ran
        job.tables_created = tables
        job.save()
        ddl_log.record(
            workspace.pk,
            job.owner,
            f"import: dump of {ran} statements, {tables} tables"
            + (" (replaced the old tables)" if job.replace else ""),
        )
        logger.info(
            "Import %s done: %s statements, %s tables, %.1fs",
            job.pk,
            ran,
            tables,
            time.monotonic() - started,
        )
    finally:
        storage.delete(job.object_key)
        quota.forget(workspace.pk)
        schema_version.bump(workspace.pk)


def expire_if_stale(job: ImportJob) -> ImportJob:
    """A job stuck `running` after a restart is shown as failed."""
    if job.status == ImportJob.RUNNING:
        age = time.time() - job.updated_at.timestamp()
        if age > STALE_AFTER_SECONDS:
            ImportJob.objects.filter(pk=job.pk, status=ImportJob.RUNNING).update(
                status=ImportJob.FAILED,
                error_code=CODE_INTERRUPTED,
                error_message="The import was interrupted. Upload the dump again.",
                updated_at=F("updated_at"),
            )
            job.refresh_from_db()
    return job
