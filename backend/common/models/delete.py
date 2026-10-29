from django.db import models
from django.utils import timezone

from common.cache.manager import cache_manager


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        """Every .filter(...).delete() call on this queryset goes through
        here — there is no way to call the 'plain' version without going
        out of your way to use hard_delete() instead."""
        cache_manager.invalidate_for_queryset(self)
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        cache_manager.invalidate_for_queryset(self)
        return super().delete()

    def active_records(self):
        return self.filter(is_deleted=False)

    def deleted_records(self):
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    def get_queryset(self) -> models.QuerySet:
        return SoftDeleteQuerySet(self.model, using=self._db).active_records()


class SoftDeleteModel(models.Model):
    is_deleted = models.BooleanField(default=False)

    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    # Declared after `objects` so `objects` stays the default manager.
    all_objects = models.Manager()  # noqa: DJ012

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):

        self.is_deleted = True

        self.deleted_at = timezone.now()

        self.save(update_fields=["is_deleted", "deleted_at"])
