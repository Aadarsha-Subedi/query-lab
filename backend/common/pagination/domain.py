"""Offset pagination for ninja's `@paginate`. The default and maximum page
sizes come from settings (PAGINATION_DEFAULT_LIMIT, PAGINATION_MAX_LIMIT).

    @router.get("/things", response=list[ThingOut])
    @paginate(OffsetPagination)
    def things(request): return Thing.objects.all()

Responds with {items, count, limit, offset}."""

from typing import Any

from django.conf import settings
from django.db.models import QuerySet
from django.http import HttpRequest
from ninja import Field, Schema
from ninja.pagination import PaginationBase


class OffsetPagination(PaginationBase):
    class Input(Schema):
        limit: int | None = Field(None, ge=1)
        offset: int = Field(0, ge=0)

    class Output(Schema):
        items: list[Any]
        count: int
        limit: int
        offset: int

    def paginate_queryset(
        self,
        queryset: QuerySet,
        pagination: Input,
        request: HttpRequest,
        **params: Any,
    ) -> dict[str, Any]:
        limit = min(
            pagination.limit or settings.PAGINATION_DEFAULT_LIMIT,
            settings.PAGINATION_MAX_LIMIT,
        )
        offset = pagination.offset
        return {
            "items": queryset[offset : offset + limit],
            "count": self._items_count(queryset),
            "limit": limit,
            "offset": offset,
        }
