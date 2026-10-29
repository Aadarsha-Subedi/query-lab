"""Reusable ninja FilterSchemas for models built on the common model mixins.
Combine them with a model's own fields:

    class ThingFilter(TimeStampFilter):
        name: Annotated[str | None, FilterLookup("name__icontains")] = None
"""

from datetime import datetime
from typing import Annotated

from ninja import FilterLookup, FilterSchema


class TimeStampFilter(FilterSchema):
    """For any model inheriting TimeStampModel."""

    created_after: Annotated[datetime | None, FilterLookup("created_at__gte")] = None
    created_before: Annotated[datetime | None, FilterLookup("created_at__lte")] = None
    updated_after: Annotated[datetime | None, FilterLookup("updated_at__gte")] = None
    updated_before: Annotated[datetime | None, FilterLookup("updated_at__lte")] = None


class SoftDeleteFilter(FilterSchema):
    """For any model inheriting SoftDeleteModel (query `all_objects`)."""

    is_deleted: Annotated[bool | None, FilterLookup("is_deleted")] = None
    deleted_after: Annotated[datetime | None, FilterLookup("deleted_at__gte")] = None
    deleted_before: Annotated[datetime | None, FilterLookup("deleted_at__lte")] = None
