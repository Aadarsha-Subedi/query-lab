"""Run a dump import: the one place a workspace is written to.

Everything happens in ONE transaction on the workspace's own `_rw` login, so a
dump either lands completely or leaves the workspace as it was (with `replace`,
the old tables are dropped inside that same transaction). The dump is read from
R2 as a stream and checked statement by statement (see `dump.py`). Caps are
checked before the commit: statements, tables, columns, foreign keys, and the
workspace and user size. The `_rw` role is the real boundary, as in the SQL
console; nothing here connects as the platform owner.

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
CODE_TOO_MANY_STATEMENTS = "dump_too_many_statements"
CODE_TOO_MANY_TABLES = "dump_too_many_tables"
CODE_TOO_MANY_COLUMNS = "dump_too_many_columns"
CODE_TOO_MANY_RELATIONS = "dump_too_many_relations"
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
WHERE n.nspname = %s AND c.relkind IN ('r', 'p', 'v', 'f', 'S') AND NOT EXISTS (
    SELECT 1 FROM pg_depend d WHERE d.objid = c.oid AND d.deptype IN ('a', 'i')
)
"""
COUNTS_SQL = """
SELECT
  (SELECT count(*) FROM pg_class c WHERE c.relnamespace = n.oid AND c.relkind IN ('r','p')),
  (SELECT coalesce(max(cnt), 0) FROM (
      SELECT count(*) AS cnt FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid
      WHERE c.relnamespace = n.oid AND c.relkind IN ('r','p')
        AND a.attnum > 0 AND NOT a.attisdropped GROUP BY a.attrelid) t),
  (SELECT count(*) FROM pg_constraint k WHERE k.connamespace = n.oid AND k.contype = 'f')
FROM pg_namespace n WHERE n.nspname = %s
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


def _existing_objects(
    connection: psycopg.Connection, schema_name: str
) -> list[tuple[str, str]]:
    return [
        (str(name), str(kind))
        for name, kind in connection.execute(TABLES_SQL, [schema_name]).fetchall()
    ]


def _clear(connection: psycopg.Connection, schema_name: str) -> None:
    """Drop every table, view and sequence of the workspace (replace mode)."""
    for name, kind in _existing_objects(connection, schema_name):
        noun = {"v": "VIEW", "S": "SEQUENCE", "f": "FOREIGN TABLE"}.get(kind, "TABLE")
        connection.execute(
            sql.SQL("DROP {} IF EXISTS {}.{} CASCADE").format(
                sql.SQL(noun), sql.Identifier(schema_name), sql.Identifier(name)
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


def _check_shape(connection: psycopg.Connection, schema_name: str) -> int:
    tables, widest, foreign_keys = connection.execute(
        COUNTS_SQL, [schema_name]
    ).fetchone() or (0, 0, 0)
    if tables > settings.WORKSPACE_MAX_TABLES:
        raise Failure(
            CODE_TOO_MANY_TABLES,
            f"The dump has {tables} tables; the limit is {settings.WORKSPACE_MAX_TABLES}.",
        )
    if widest > settings.WORKSPACE_MAX_COLUMNS:
        raise Failure(
            CODE_TOO_MANY_COLUMNS,
            f"A table has {widest} columns; the limit is {settings.WORKSPACE_MAX_COLUMNS}.",
        )
    if foreign_keys > settings.WORKSPACE_MAX_RELATIONS:
        raise Failure(
            CODE_TOO_MANY_RELATIONS,
            f"The dump has {foreign_keys} foreign keys; "
            f"the limit is {settings.WORKSPACE_MAX_RELATIONS}.",
        )
    return int(tables)


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
        elif _existing_objects(connection, workspace.schema_name):
            raise Failure(
                CODE_NOT_EMPTY,
                "This workspace already has tables. Use Replace data.",
            )
        try:
            for item in dump.read(lines):
                ran += 1
                if ran > settings.DUMP_MAX_STATEMENTS:
                    raise Failure(
                        CODE_TOO_MANY_STATEMENTS,
                        f"At most {settings.DUMP_MAX_STATEMENTS} statements.",
                        item.number,
                        item.line,
                    )
                _execute(connection, item, workspace)
                if item.kind == "copy" or ran % SIZE_CHECK_EVERY == 0:
                    _check_size(connection, workspace, final=False)
        except dump.DumpRefused as refused:
            raise Failure(
                CODE_REFUSED, refused.message, refused.number, refused.line
            ) from None
        except UnicodeDecodeError:
            raise Failure(CODE_ENCODING, "The dump must be UTF-8 text.") from None
        tables = _check_shape(connection, workspace.schema_name)
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
