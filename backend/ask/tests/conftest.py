import pytest

from ask.schema import Column, ForeignKey, Schema, Table


def _table(
    name: str, columns: dict[str, str], pk: tuple[str, ...] = (), fks=()
) -> Table:
    return Table(
        name=name,
        comment=f"The {name} table.",
        columns=tuple(Column(c, t, True, f"The {c}.") for c, t in columns.items()),
        primary_key=pk,
        foreign_keys=tuple(fks),
    )


@pytest.fixture
def small_schema() -> Schema:
    """A hand-built slice of the Olist schema, so guard tests need no database."""
    return Schema(
        name="demo",
        tables=(
            _table(
                "orders",
                {
                    "order_id": "text",
                    "customer_id": "text",
                    "order_status": "text",
                    "order_purchase_timestamp": "timestamp without time zone",
                },
                ("order_id",),
                [ForeignKey(("customer_id",), "customers", ("customer_id",))],
            ),
            _table(
                "customers",
                {
                    "customer_id": "text",
                    "customer_city": "text",
                    "customer_state": "text",
                },
                ("customer_id",),
            ),
            _table(
                "order_items",
                {"order_id": "text", "price": "numeric(10,2)", "product_id": "text"},
            ),
        ),
    )
