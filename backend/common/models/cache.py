from typing import Any

from django.db import models

from common.cache.manager import cache_manager


class CacheModel(models.Model):
    """Opt-in mixin — only inherit this on models that are actually read
    through the cache. Provides automatic invalidation on save()/delete()
    so call sites never need to remember to clear the cache manually."""

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        super().save(*args, **kwargs)
        cache_manager.delete(self.cache_key())

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        result = super().delete(*args, **kwargs)
        cache_manager.delete(self.cache_key())
        return result

    def cache_key(self) -> str:
        return f"{self._meta.model_name}:{self.pk}"
