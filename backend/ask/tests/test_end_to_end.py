"""About 15 typical Olist questions through the whole path (guard, runner,
response) with a fake LLM that answers with known-good SQL. Each answer is
compared with the same SQL run directly as the reader role, so the guard's
rewrites (schema, aliases, LIMIT) must not change what comes back."""

import json
from typing import Any

import psycopg
import pytest
from django.test import Client

from accounts.models import User
from ask import keys
from common.llm.fake import FakeProvider

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("data_connections")]

QUESTIONS = [
    ("How many orders are there?", "SELECT count(*) AS orders FROM demo.orders"),
    (
        "Orders by status, most common first?",
        "SELECT order_status, count(*) AS n FROM demo.orders GROUP BY order_status ORDER BY n DESC, order_status",
    ),
    (
        "Which 5 states have the most customers?",
        "SELECT customer_state, count(*) AS customers FROM demo.customers GROUP BY customer_state ORDER BY customers DESC, customer_state LIMIT 5",
    ),
    (
        "Total revenue from delivered orders?",
        "SELECT round(sum(oi.price), 2) AS revenue FROM demo.order_items oi JOIN demo.orders o ON o.order_id = oi.order_id WHERE o.order_status = 'delivered'",
    ),
    (
        "Orders per month?",
        "SELECT date_trunc('month', order_purchase_timestamp) AS month, count(*) AS n FROM demo.orders GROUP BY 1 ORDER BY 1",
    ),
    (
        "Top 10 product categories by items sold, in English?",
        "SELECT t.product_category_name_english AS category, count(*) AS items FROM demo.order_items oi JOIN demo.products p ON p.product_id = oi.product_id JOIN demo.product_category_translation t ON t.product_category_name = p.product_category_name GROUP BY 1 ORDER BY items DESC, category LIMIT 10",
    ),
    (
        "Average review score?",
        "SELECT round(avg(review_score), 2) AS avg_score FROM demo.order_reviews",
    ),
    (
        "How many sellers per state?",
        "SELECT seller_state, count(*) AS sellers FROM demo.sellers GROUP BY 1 ORDER BY sellers DESC, seller_state",
    ),
    (
        "Payment types and how often each is used?",
        "SELECT payment_type, count(*) AS uses FROM demo.order_payments GROUP BY 1 ORDER BY uses DESC, payment_type",
    ),
    (
        "Average order value by payment type?",
        "SELECT payment_type, round(avg(payment_value), 2) AS avg_value FROM demo.order_payments GROUP BY 1 ORDER BY 1",
    ),
    (
        "Customers with more than one order?",
        "SELECT count(*) AS repeat_customers FROM (SELECT customer_unique_id FROM demo.customers GROUP BY 1 HAVING count(*) > 1) t",
    ),
    (
        "Share of orders that were canceled?",
        "SELECT round(100.0 * count(*) FILTER (WHERE order_status = 'canceled') / count(*), 2) AS pct FROM demo.orders",
    ),
    (
        "Ten most expensive items sold?",
        "SELECT product_id, price FROM demo.order_items ORDER BY price DESC, product_id LIMIT 10",
    ),
    (
        "Orders delivered late (after the estimate)?",
        "SELECT count(*) AS late FROM demo.orders WHERE order_delivered_customer_date > order_estimated_delivery_date",
    ),
    (
        "Which city has the most customers?",
        "WITH c AS (SELECT customer_city, count(*) AS n FROM demo.customers GROUP BY 1) SELECT customer_city, n FROM c ORDER BY n DESC, customer_city LIMIT 1",
    ),
]


@pytest.mark.parametrize(("question", "sql"), QUESTIONS, ids=[q for q, _ in QUESTIONS])
def test_answer_matches_the_sql_run_directly(
    client: Client,
    user: User,
    reader: psycopg.Connection,
    monkeypatch: pytest.MonkeyPatch,
    question: str,
    sql: str,
) -> None:
    fake = FakeProvider(
        answers=[json.dumps({"sql": sql, "rationale": "r", "self_confidence": 0.9})]
    )
    monkeypatch.setattr(
        keys,
        "resolve_provider",
        lambda u: keys.ResolvedProvider(fake, "gemini", keys.KEY_OWN),
    )
    client.force_login(user)
    response = client.post(
        "/api/ask", json.dumps({"question": question}), content_type="application/json"
    )
    assert response.status_code == 200, response.content
    data = response.json()["data"]

    cursor = reader.execute(sql)
    expected = [list(map(_plain, row)) for row in cursor.fetchall()]
    assert data["columns"] == [col.name for col in cursor.description or []]
    assert [[_plain(v) for v in row] for row in data["rows"]] == [
        [_plain(v) for v in row] for row in expected
    ]
    assert data["row_count"] == len(expected)


def _plain(value: Any) -> Any:
    """Compare across types the API turns into strings (Decimal, dates)."""
    return None if value is None else str(value).replace(" ", "T")
