import hashlib
from collections.abc import Callable, Sequence
from typing import TypeVar, cast

from django.conf import settings
from django.core.cache import cache
from django.db import models

T = TypeVar("T")


class CacheManager:
    def __init__(self, timeout: int | None = None):
        # Read lazily so tests can override the setting.
        self._timeout = timeout

    @property
    def timeout(self) -> int:
        if self._timeout is not None:
            return self._timeout
        return settings.CACHE_DEFAULT_TIMEOUT_SECONDS

    def get(self, key: str) -> object | None:
        return cache.get(key)

    def add(self, key: str, value: object, timeout: int | None = None) -> None:
        cache.set(key, value, timeout=timeout or self.timeout)

    def update(self, key: str, value: object, timeout: int | None = None) -> None:
        # functionally identical to add() — cache.set() always overwrites.
        # kept separate for readability at call sites: "update" signals intent
        # even though the underlying operation is the same.
        cache.set(key, value, timeout=timeout or self.timeout)

    def delete(self, key: str) -> None:
        cache.delete(key)

    def delete_many(self, keys: list[str]) -> None:
        cache.delete_many(keys)

    def get_or_set(
        self,
        key: str,
        loader: Callable[[], T],
        timeout: int | None = None,
        should_cache: Callable[[T], bool] | None = None,
        serialize: Callable[[T], object] | None = None,
        deserialize: Callable[[object], T] | None = None,
    ) -> T:

        cached = self.get(key)

        if cached is not None:
            return deserialize(cached) if deserialize else cast(T, cached)

        value = loader()

        if should_cache is None or should_cache(value):
            to_store = serialize(value) if serialize else value

            self.add(key, to_store, timeout)

        return value

    def keys_for(
        self, model: type[models.Model], primary_keys: list[object]
    ) -> list[str]:
        """The single source of truth for how a bulk set of cache keys is
        built for a given model + list of primary keys. Every queryset/mixin that
        needs bulk invalidation routes through this — not its own f-string."""
        if not primary_keys:
            return []

        model_name = model._meta.model_name

        return [f"{model_name}:{primary_key}" for primary_key in primary_keys]

    def invalidate_for_queryset(self, queryset: models.QuerySet) -> None:
        """Convenience wrapper: given a queryset, look up its model's pks and
        delete every matching cache key in one batched call. Only does
        anything if the model actually opts into caching."""

        if not hasattr(queryset.model, "cache_key"):
            return

        pks = list(queryset.values_list("pk", flat=True))

        self.delete_many(self.keys_for(queryset.model, pks))

    def invalidate_for_objects(self, objects: Sequence[models.Model]) -> None:
        """Given a list of already-loaded instances, invalidate without
        re-querying — use when you already have the objects in memory
        (e.g. just bulk_created or bulk_updated them)."""

        if not objects:
            return

        model = type(objects[0])

        if not hasattr(model, "cache_key"):
            return

        pks = [obj.pk for obj in objects]

        self.delete_many(self.keys_for(model, pks))

    def build_scoped_key(self, namespace: str, *parts: str) -> str:
        """General-purpose scoped key builder for anything that isn't
        model-backed (model-backed keys should use keys_for instead).
        Joins parts, hashes for a fixed-length, collision-resistant key."""

        raw = ":".join(p for p in parts)

        digest = hashlib.sha256(raw.encode()).hexdigest()

        return f"{namespace}:{digest}"


cache_manager = CacheManager()
