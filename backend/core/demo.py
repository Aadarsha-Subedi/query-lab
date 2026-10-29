"""Loads the Olist CSVs into the demo schema.

Each CSV is streamed with COPY into a temporary all-text staging table, then
inserted into the typed table with the clean-ups applied on the way:
product categories translated to English and every date shifted forward by
DEMO_DATE_SHIFT_DAYS. Everything runs in one transaction after a TRUNCATE, so
a re-run replaces the data and a failed run leaves the old data in place.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.db import connections
from psycopg import sql

from core.datadb import DEMO_SCHEMA


@dataclass(frozen=True)
class DemoTable:
    name: str
    csv_file: str
    # Target columns, and the SELECT over the staging table `s` that fills
    # them. {shift} is the date offset; {schema} the target schema.
    columns: str
    select: str


def _shifted(column: str) -> str:
    return f"NULLIF(s.{column}, '')::timestamp + {{shift}}"


def _int(column: str) -> str:
    return f"NULLIF(s.{column}, '')::integer"


# In foreign-key order.
TABLES: tuple[DemoTable, ...] = (
    DemoTable(
        "product_category_translation",
        "product_category_name_translation.csv",
        "product_category_name, product_category_name_english",
        "SELECT s.product_category_name, s.product_category_name_english FROM {staging} s",
    ),
    DemoTable(
        "customers",
        "olist_customers_dataset.csv",
        "customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state",
        "SELECT s.customer_id, s.customer_unique_id, s.customer_zip_code_prefix,"
        " s.customer_city, s.customer_state FROM {staging} s",
    ),
    DemoTable(
        "sellers",
        "olist_sellers_dataset.csv",
        "seller_id, seller_zip_code_prefix, seller_city, seller_state",
        "SELECT s.seller_id, s.seller_zip_code_prefix, s.seller_city, s.seller_state"
        " FROM {staging} s",
    ),
    DemoTable(
        "products",
        "olist_products_dataset.csv",
        "product_id, product_category_name, product_name_length,"
        " product_description_length, product_photos_qty, product_weight_g,"
        " product_length_cm, product_height_cm, product_width_cm",
        # Categories without a translation keep their Portuguese name.
        "SELECT s.product_id,"
        " COALESCE(t.product_category_name_english, NULLIF(s.product_category_name, '')),"
        f" {_int('product_name_lenght')}, {_int('product_description_lenght')},"
        f" {_int('product_photos_qty')}, {_int('product_weight_g')},"
        f" {_int('product_length_cm')}, {_int('product_height_cm')},"
        f" {_int('product_width_cm')}"
        " FROM {staging} s LEFT JOIN {schema}.product_category_translation t"
        " ON t.product_category_name = s.product_category_name",
    ),
    DemoTable(
        "orders",
        "olist_orders_dataset.csv",
        "order_id, customer_id, order_status, order_purchase_timestamp,"
        " order_approved_at, order_delivered_carrier_date,"
        " order_delivered_customer_date, order_estimated_delivery_date",
        "SELECT s.order_id, s.customer_id, s.order_status,"
        f" {_shifted('order_purchase_timestamp')}, {_shifted('order_approved_at')},"
        f" {_shifted('order_delivered_carrier_date')},"
        f" {_shifted('order_delivered_customer_date')},"
        f" {_shifted('order_estimated_delivery_date')}"
        " FROM {staging} s",
    ),
    DemoTable(
        "order_items",
        "olist_order_items_dataset.csv",
        "order_id, order_item_id, product_id, seller_id, shipping_limit_date,"
        " price, freight_value",
        f"SELECT s.order_id, {_int('order_item_id')}, s.product_id, s.seller_id,"
        f" {_shifted('shipping_limit_date')}, s.price::numeric, s.freight_value::numeric"
        " FROM {staging} s",
    ),
    DemoTable(
        "order_payments",
        "olist_order_payments_dataset.csv",
        "order_id, payment_sequential, payment_type, payment_installments, payment_value",
        f"SELECT s.order_id, {_int('payment_sequential')}, s.payment_type,"
        f" {_int('payment_installments')}, s.payment_value::numeric FROM {{staging}} s",
    ),
    DemoTable(
        "order_reviews",
        "olist_order_reviews_dataset.csv",
        "review_id, order_id, review_score, review_comment_title,"
        " review_comment_message, review_creation_date, review_answer_timestamp",
        f"SELECT s.review_id, s.order_id, {_int('review_score')},"
        " NULLIF(s.review_comment_title, ''), NULLIF(s.review_comment_message, ''),"
        f" {_shifted('review_creation_date')}, {_shifted('review_answer_timestamp')}"
        " FROM {staging} s",
    ),
    DemoTable(
        "geolocation",
        "olist_geolocation_dataset.csv",
        "geolocation_zip_code_prefix, geolocation_lat, geolocation_lng,"
        " geolocation_city, geolocation_state",
        "SELECT s.geolocation_zip_code_prefix, s.geolocation_lat::double precision,"
        " s.geolocation_lng::double precision, s.geolocation_city, s.geolocation_state"
        " FROM {staging} s",
    ),
)


def csv_header(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def csv_row_count(path: Path) -> int:
    """Records, not lines: review texts contain newlines inside quotes."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.reader(handle)) - 1


def load(
    source_dir: Path,
    shift_days: int,
    schema: str = DEMO_SCHEMA,
) -> dict[str, int]:
    """Replace the demo tables in `schema` with the CSVs in `source_dir`.
    Returns the row count of each table."""
    missing = [t.csv_file for t in TABLES if not (source_dir / t.csv_file).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing in {source_dir}: {', '.join(missing)}")

    schema_id = sql.Identifier(schema)
    shift = sql.SQL("make_interval(days => {})").format(sql.Literal(shift_days))
    connection = connections[settings.DATA_DB_ALIAS]
    connection.ensure_connection()
    raw = connection.connection
    counts: dict[str, int] = {}
    with raw.transaction(), raw.cursor() as cursor:
        cursor.execute(
            sql.SQL("TRUNCATE {} RESTART IDENTITY").format(
                sql.SQL(", ").join(
                    sql.Identifier(schema, table.name) for table in TABLES
                )
            )
        )
        for table in TABLES:
            path = source_dir / table.csv_file
            staging = sql.Identifier(f"staging_{table.name}")
            header = csv_header(path)
            cursor.execute(
                sql.SQL("CREATE TEMP TABLE {} ({}) ON COMMIT DROP").format(
                    staging,
                    sql.SQL(", ").join(
                        sql.SQL("{} text").format(sql.Identifier(column))
                        for column in header
                    ),
                )
            )
            copy_sql = sql.SQL("COPY {} FROM STDIN WITH (FORMAT csv, HEADER true)")
            with (
                path.open("rb") as handle,
                cursor.copy(copy_sql.format(staging)) as copy,
            ):
                for line in handle:
                    copy.write(line)
            cursor.execute(
                sql.SQL("INSERT INTO {} ({}) ").format(
                    sql.Identifier(schema, table.name), sql.SQL(table.columns)
                )
                + sql.SQL(table.select).format(
                    staging=staging, schema=schema_id, shift=shift
                )
            )
            cursor.execute(
                sql.SQL("SELECT count(*) FROM {}").format(
                    sql.Identifier(schema, table.name)
                )
            )
            row = cursor.fetchone()
            counts[table.name] = row[0] if row else 0
    return counts
