"""Cloudflare R2 (S3 API) for dump uploads.

The browser PUTs the file straight to the bucket with a presigned URL, so the
bytes never pass through the 1/4 vCPU container. The import job reads the object
back as a stream of text lines (gunzipped when the key ends in `.gz`) and deletes
it afterwards. Objects live under `dumps/<user>/<workspace>/<token>.sql[.gz]`; a
bucket lifecycle rule (delete after 1 day) is the safety net for abandoned ones.

boto3 is imported on first use: it is slow to import and the web process does not
need it until a dump is uploaded.
"""

import contextlib
import gzip
import io
import secrets
from collections.abc import Iterator
from functools import lru_cache
from typing import Any

from django.conf import settings

from workspaces.errors import DumpTooLarge, DumpUploadMissing

SUFFIXES = (".sql", ".sql.gz")


@lru_cache(maxsize=1)
def _client() -> Any:
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=5,
            read_timeout=30,
        ),
    )


def new_key(user_id: int, workspace_id: int, *, gzipped: bool) -> str:
    """A key nobody can guess; the owner and workspace are part of the path so a
    job can check the object is the one it expects."""
    suffix = ".sql.gz" if gzipped else ".sql"
    return f"dumps/{user_id}/{workspace_id}/{secrets.token_urlsafe(24)}{suffix}"


def key_belongs_to(key: str, user_id: int, workspace_id: int) -> bool:
    return key.startswith(f"dumps/{user_id}/{workspace_id}/") and key.endswith(SUFFIXES)


def presign_put(key: str, size: int) -> str:
    """A URL that accepts exactly one PUT of exactly `size` bytes to `key`: the
    length is part of the signature, so the browser cannot send more."""
    if size > settings.DUMP_MAX_FILE_BYTES:
        raise DumpTooLarge()
    return _client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": key,
            "ContentLength": size,
        },
        ExpiresIn=settings.DUMP_PRESIGN_SECONDS,
    )


def stored_size(key: str) -> int:
    """The size of the uploaded object; DumpUploadMissing when it is not there."""
    from botocore.exceptions import ClientError

    try:
        head = _client().head_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "")
        if code in {"404", "NoSuchKey", "NotFound"}:
            raise DumpUploadMissing() from None
        raise
    size = int(head["ContentLength"])
    if size > settings.DUMP_MAX_FILE_BYTES:
        raise DumpTooLarge()
    return size


def read_lines(key: str, *, max_text_bytes: int) -> Iterator[str]:
    """The object as text lines. `max_text_bytes` caps the decompressed size, so a
    small gzip bomb cannot fill memory or the database."""
    body = _client().get_object(Bucket=settings.R2_BUCKET_NAME, Key=key)["Body"]
    try:
        raw: Any = gzip.GzipFile(fileobj=body) if key.endswith(".gz") else body
        total = 0
        # errors="strict": a dump that is not UTF-8 fails clearly instead of
        # storing replacement characters.
        for line in io.TextIOWrapper(raw, encoding="utf-8", errors="strict"):
            total += len(line)
            if total > max_text_bytes:
                raise DumpTooLarge()
            yield line
    finally:
        body.close()


def delete(key: str) -> None:
    """Best effort: the lifecycle rule removes anything left behind."""
    from botocore.exceptions import BotoCoreError, ClientError

    with contextlib.suppress(BotoCoreError, ClientError):
        _client().delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
