import time
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from accounts.models import User
from evals import clustering
from evals.clustering import Item, cluster, features, group_key
from evals.models import TraceCase

JOIN = (
    "SELECT c.customer_state, count(*) FROM orders o "
    "JOIN customers c ON c.customer_id = o.customer_id WHERE o.order_status = '{}' "
    "GROUP BY c.customer_state"
)


def test_features_name_tables_and_shape() -> None:
    f = features("answered", JOIN.format("delivered"))
    assert f.tables == ("customers", "orders")
    assert f.shape == "j1|agg:count|group"


def test_literals_do_not_change_the_fingerprint() -> None:
    a = features("answered", JOIN.format("delivered"))
    b = features("answered", JOIN.format("canceled"))
    assert a == b and group_key(a) == group_key(b)


def test_shape_notices_window_nested_and_top_n() -> None:
    assert (
        "window" in features("a", "SELECT rank() OVER (ORDER BY x) FROM orders").shape
    )
    assert (
        "nested"
        in features("a", "WITH t AS (SELECT 1 FROM orders) SELECT * FROM t").shape
    )
    assert features("a", "WITH t AS (SELECT 1 FROM orders) SELECT * FROM t").tables == (
        "orders",
    )
    assert "topn" in features("a", "SELECT x FROM orders ORDER BY x LIMIT 5").shape


def test_no_sql_and_broken_sql_have_their_own_shapes() -> None:
    assert features("declined", "").shape == "none"
    assert features("error", "SELEC ((").shape in ("unparsed", "j0")


def test_different_tables_or_outcomes_get_different_keys() -> None:
    a = group_key(features("answered", "SELECT 1 FROM orders"))
    assert a != group_key(features("answered", "SELECT 1 FROM customers"))
    assert a != group_key(features("error", "SELECT 1 FROM orders"))


def items(*rows: tuple[int, str, str, str]) -> list[Item]:
    return [Item(*row) for row in rows]


def test_same_pattern_phrased_differently_merges() -> None:
    keys = cluster(
        items(
            (
                1,
                "answered",
                "SELECT count(*) FROM orders",
                "How many orders are there?",
            ),
            (
                2,
                "answered",
                "SELECT count(*), 1 FROM orders GROUP BY 2",
                "Total number of orders",
            ),
            (
                3,
                "answered",
                "SELECT count(*) FROM orders",
                "Number of orders placed in total",
            ),
        ),
        0.3,
    )
    assert keys[1] == keys[3]
    # 2 has another shape (grouped) but overlapping words: layer 2 joins it
    assert keys[1] == keys[2]


def test_different_tables_never_merge() -> None:
    keys = cluster(
        items(
            (
                1,
                "answered",
                "SELECT count(*) FROM orders",
                "How many orders are there?",
            ),
            (
                2,
                "answered",
                "SELECT count(*) FROM customers",
                "How many orders are there?",
            ),
        ),
        0.1,
    )
    assert keys[1] != keys[2]


def test_unrelated_questions_stay_apart_and_threshold_matters() -> None:
    rows = items(
        (1, "answered", "SELECT count(*) FROM orders", "revenue by month"),
        (2, "answered", "SELECT count(*), 1 FROM orders GROUP BY 2", "late deliveries"),
    )
    assert cluster(rows, 0.5)[1] != cluster(rows, 0.5)[2]
    assert cluster(rows, 0.0)[1] == cluster(rows, 0.0)[2]


def test_reruns_and_input_order_give_identical_clusters() -> None:
    rows = items(
        (3, "answered", "SELECT count(*) FROM orders", "orders count please"),
        (1, "answered", "SELECT count(*) FROM orders", "count orders"),
        (2, "error", "", "weather today"),
    )
    assert (
        cluster(rows, 0.4) == cluster(list(reversed(rows)), 0.4) == cluster(rows, 0.4)
    )


def test_empty_and_single() -> None:
    assert cluster([], 0.5) == {}
    only = cluster(items((7, "answered", "SELECT 1 FROM orders", "x")), 0.5)
    assert list(only) == [7]


def test_a_thousand_runs_cluster_quickly() -> None:
    rows = [
        Item(
            n,
            "answered",
            f"SELECT count(*) FROM orders WHERE x = {n}",
            f"orders count for customer {n} in region {n % 7}",
        )
        for n in range(1000)
    ]
    started = time.perf_counter()
    keys = cluster(rows, 0.5)
    assert time.perf_counter() - started < 10
    assert len(keys) == 1000


def test_stopwords_are_ignored() -> None:
    assert clustering.words("How many orders are there?") == {"orders"}


@pytest.mark.django_db
class TestStored:
    def make(
        self,
        n: int,
        question: str,
        sql: str,
        signals: int = 1,
        outcome: str = "answered",
    ) -> TraceCase:
        return TraceCase.objects.create(
            source_run_id=n,
            source_created_at=timezone.now() + timedelta(minutes=n),
            question=question,
            reasons="failed",
            signals=signals,
            outcome=outcome,
            source_sql=sql,
        )

    def test_assign_summaries_and_representative(self) -> None:
        a = self.make(1, "count orders", "SELECT count(*) FROM orders")
        b = self.make(2, "orders count", "SELECT count(*) FROM orders", signals=3)
        c = self.make(
            3, "late deliveries", "SELECT 1 FROM order_reviews", outcome="error"
        )
        assert clustering.assign_clusters() == 3
        assert clustering.assign_clusters() == 0
        for case in (a, b, c):
            case.refresh_from_db()
        assert a.cluster_key == b.cluster_key != c.cluster_key
        first, second = clustering.summaries()
        assert first.size == 2 and first.representative_id == b.pk
        assert first.status_counts == {"candidate": 2}
        assert second.size == 1 and "order_reviews" in second.label

    def test_the_cap_limits_a_pass(self, settings) -> None:
        settings.TRACES_CLUSTER_MAX_RUNS = 2
        for n in range(1, 5):
            self.make(n, f"q{n}", "SELECT 1 FROM orders")
        assert clustering.assign_clusters() == 2

    def test_the_endpoint_lists_clusters_for_staff(self, client: Client) -> None:
        self.make(1, "count orders", "SELECT count(*) FROM orders")
        clustering.assign_clusters()
        client.force_login(User.objects.create_user("s@example.com", is_staff=True))
        body = client.get("/api/workbench/clusters").json()
        assert body["meta"]["count"] == 1
        row = body["data"][0]
        assert row["size"] == 1 and row["label"].startswith("answered on orders")
