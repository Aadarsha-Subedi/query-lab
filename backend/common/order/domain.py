"""`?ordering=-created_at,name` for ninja endpoints, limited to an allowlist.

class ThingOrdering(OrderingSchema):
    allowed_fields = [*TIMESTAMP_ORDERING_FIELDS, "name"]

def things(request, ordering: Query[ThingOrdering]):
    return ordering.apply(Thing.objects.all())
"""

from typing import ClassVar

from django.db.models import QuerySet
from ninja import Schema
from pydantic import field_validator

from common.order.constants import TIMESTAMP_ORDERING_FIELDS


class OrderingSchema(Schema):
    allowed_fields: ClassVar[list[str]] = TIMESTAMP_ORDERING_FIELDS

    ordering: str | None = None

    @field_validator("ordering")
    @classmethod
    def only_allowed_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        for term in cls.terms(value):
            if term.lstrip("-") not in cls.allowed_fields:
                raise ValueError(
                    f"Cannot order by '{term}'. Allowed: {', '.join(cls.allowed_fields)}."
                )
        return value

    @staticmethod
    def terms(value: str) -> list[str]:
        return [term.strip() for term in value.split(",") if term.strip()]

    def apply(self, queryset: QuerySet) -> QuerySet:
        return (
            queryset.order_by(*self.terms(self.ordering)) if self.ordering else queryset
        )
