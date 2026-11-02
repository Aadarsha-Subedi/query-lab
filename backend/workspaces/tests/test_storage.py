import gzip
import io
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from django.test import override_settings

from workspaces import storage
from workspaces.errors import DumpTooLarge, DumpUploadMissing

R2 = {
    "R2_ENDPOINT_URL": "https://acct.r2.cloudflarestorage.com",
    "R2_ACCESS_KEY_ID": "AKIATEST",
    "R2_SECRET_ACCESS_KEY": "secret",
    "R2_BUCKET_NAME": "dumps-test",
    "DUMP_MAX_FILE_BYTES": 1000,
    "DUMP_PRESIGN_SECONDS": 600,
}


@pytest.fixture(autouse=True)
def fresh_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test builds its own client (and monkeypatch restores the real one)."""
    storage._client.cache_clear()
    monkeypatch.setattr(storage, "_client", storage._client)


class FakeBody(io.BytesIO):
    pass


class FakeClient:
    def __init__(self, data: bytes = b"", missing: bool = False):
        self.data = data
        self.missing = missing
        self.deleted: list[str] = []

    def head_object(self, **kwargs: Any) -> dict[str, int]:
        from botocore.exceptions import ClientError

        if self.missing:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {"ContentLength": len(self.data)}

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        return {"Body": FakeBody(self.data)}

    def delete_object(self, **kwargs: Any) -> None:
        self.deleted.append(kwargs["Key"])


@override_settings(**R2)
def test_presigned_url_pins_key_size_and_expiry() -> None:
    key = storage.new_key(7, 3, gzipped=False)
    url = storage.presign_put(key, 500)
    parsed = urlparse(url)
    assert parsed.netloc == "acct.r2.cloudflarestorage.com"
    assert parsed.path == f"/dumps-test/{key}"
    query = parse_qs(parsed.query)
    assert query["X-Amz-Expires"] == ["600"]
    assert "content-length" in query["X-Amz-SignedHeaders"][0]


@override_settings(**R2)
def test_presign_refuses_a_file_over_the_cap() -> None:
    with pytest.raises(DumpTooLarge):
        storage.presign_put("dumps/1/1/x.sql", 1001)


def test_keys_are_unguessable_and_scoped() -> None:
    first = storage.new_key(7, 3, gzipped=True)
    assert first.startswith("dumps/7/3/") and first.endswith(".sql.gz")
    assert first != storage.new_key(7, 3, gzipped=True)
    assert storage.key_belongs_to(first, 7, 3)
    assert not storage.key_belongs_to(first, 8, 3)
    assert not storage.key_belongs_to(first, 7, 4)
    assert not storage.key_belongs_to("dumps/7/3/x.exe", 7, 3)
    assert not storage.key_belongs_to("dumps/7/30/x.sql", 7, 3)


@override_settings(**R2)
def test_reads_plain_and_gzipped_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    text = "SELECT 1;\nSELECT 2;\n"
    monkeypatch.setattr(storage, "_client", lambda: FakeClient(text.encode()))
    assert list(storage.read_lines("k.sql", max_text_bytes=100)) == [
        "SELECT 1;\n",
        "SELECT 2;\n",
    ]
    monkeypatch.setattr(
        storage, "_client", lambda: FakeClient(gzip.compress(text.encode()))
    )
    assert "".join(storage.read_lines("k.sql.gz", max_text_bytes=100)) == text


@override_settings(**R2)
def test_decompressed_size_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    bomb = gzip.compress(b"-- x\n" * 10_000)
    monkeypatch.setattr(storage, "_client", lambda: FakeClient(bomb))
    assert len(bomb) < 1000
    with pytest.raises(DumpTooLarge):
        list(storage.read_lines("k.sql.gz", max_text_bytes=1000))


@override_settings(**R2)
def test_non_utf8_is_an_error_not_replacement_characters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(storage, "_client", lambda: FakeClient(b"INSERT '\xff';\n"))
    with pytest.raises(UnicodeDecodeError):
        list(storage.read_lines("k.sql", max_text_bytes=100))


@override_settings(**R2)
def test_stored_size_missing_and_too_big(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage, "_client", lambda: FakeClient(missing=True))
    with pytest.raises(DumpUploadMissing):
        storage.stored_size("k.sql")
    monkeypatch.setattr(storage, "_client", lambda: FakeClient(b"x" * 2000))
    with pytest.raises(DumpTooLarge):
        storage.stored_size("k.sql")
    monkeypatch.setattr(storage, "_client", lambda: FakeClient(b"x" * 10))
    assert storage.stored_size("k.sql") == 10


def test_delete_is_best_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient()
    monkeypatch.setattr(storage, "_client", lambda: client)
    storage.delete("k.sql")
    assert client.deleted == ["k.sql"]
