from django.db import models
from django.utils import timezone

from common.cache.manager import cache_manager


class BulkOperationsQuerySet(models.QuerySet):
    def update(self, **kwargs):

        kwargs.setdefault("updated_at", timezone.now())

        cache_manager.invalidate_for_queryset(self)

        return super().update(**kwargs)


class BulkOperationsModel(models.Model):
    class Meta:
        abstract = True

    @classmethod
    def bulk_create_safe(cls, objects: list, batch_size: int | None = None) -> list:

        created = cls._default_manager.bulk_create(objects, batch_size=batch_size)

        cache_manager.invalidate_for_objects(created)

        return created

    @classmethod
    def bulk_update_safe(
        cls, objects: list, fields: list[str], batch_size: int | None = None
    ) -> None:

        now = timezone.now()

        for obj in objects:
            obj.updated_at = now

        updated_fields = [*fields, "updated_at"]

        cls._default_manager.bulk_update(objects, updated_fields, batch_size=batch_size)

        cache_manager.invalidate_for_objects(objects)
