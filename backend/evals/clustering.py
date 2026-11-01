"""Group trace cases into clusters of the same kind of question (step 6).

Deterministic, no ML library, stdlib plus sqlglot (already installed):

- Layer 1: an exact key from the outcome, the set of tables and the SQL's shape.
  Literals never matter: the shape is built from structure alone.
- Layer 2: inside one outcome and table set, groups merge when their questions
  share enough words (Jaccard on word sets at TRACES_CLUSTER_SIMILARITY, single
  link). Ties go to the lowest case id, so the same cases always give the same
  clusters.

The pure functions take plain values; `assign_clusters` and `summaries` read the
cases in a bounded pass (TRACES_CLUSTER_MAX_RUNS)."""

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import sqlglot
from django.conf import settings
from sqlglot import exp
from sqlglot.errors import SqlglotError

from evals.models import TraceCase

NO_SQL_SHAPE = "none"
UNPARSED_SHAPE = "unparsed"

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "from",
        "by",
        "with",
        "and",
        "or",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "do",
        "does",
        "did",
        "how",
        "what",
        "which",
        "who",
        "whom",
        "when",
        "where",
        "why",
        "many",
        "much",
        "me",
        "my",
        "our",
        "we",
        "i",
        "you",
        "show",
        "give",
        "list",
        "tell",
        "get",
        "find",
        "there",
        "their",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "all",
        "any",
        "each",
        "per",
        "than",
        "then",
        "as",
        "has",
        "have",
        "had",
        "can",
        "could",
        "would",
        "should",
        "will",
    ]
)
WORD = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Features:
    outcome: str
    tables: tuple[str, ...]
    shape: str


@dataclass(frozen=True)
class Item:
    """What clustering needs to know about one case."""

    id: int
    outcome: str
    sql: str
    question: str


def _shape_of(tree: exp.Expr) -> str:
    joins = len(list(tree.find_all(exp.Join)))
    aggregates = sorted({node.key for node in tree.find_all(exp.AggFunc)})
    parts = [f"j{joins}"]
    if aggregates:
        parts.append("agg:" + ",".join(aggregates))
    if tree.args.get("group"):
        parts.append("group")
    if tree.find(exp.Window):
        parts.append("window")
    if tree.find(exp.Subquery) or tree.find(exp.CTE):
        parts.append("nested")
    if tree.args.get("order") and tree.args.get("limit"):
        parts.append("topn")
    return "|".join(parts)


def features(outcome: str, sql: str) -> Features:
    """Outcome class, sorted table names and a literal-free shape fingerprint."""
    if not sql.strip():
        return Features(outcome, (), NO_SQL_SHAPE)
    try:
        tree = sqlglot.parse_one(sql, read="postgres")
    except SqlglotError:
        return Features(outcome, (), UNPARSED_SHAPE)
    if tree is None:
        return Features(outcome, (), UNPARSED_SHAPE)
    ctes = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    tables = tuple(
        sorted({t.name.lower() for t in tree.find_all(exp.Table) if t.name} - ctes)
    )
    return Features(outcome, tables, _shape_of(tree))


def group_key(found: Features) -> str:
    """Layer 1: short, stable and safe to put in a tag."""
    digest = hashlib.sha1(
        f"{','.join(found.tables)}|{found.shape}".encode(), usedforsecurity=False
    ).hexdigest()[:10]
    return f"{found.outcome}/{digest}"


def words(question: str) -> frozenset[str]:
    return frozenset(w for w in WORD.findall(question.lower()) if w not in STOPWORDS)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def cluster(items: Iterable[Item], threshold: float) -> dict[int, str]:
    """Case id -> cluster key. Pure and deterministic."""
    ordered = sorted(items, key=lambda item: item.id)
    groups: dict[str, list[Item]] = {}
    family: dict[str, tuple[str, tuple[str, ...]]] = {}
    for item in ordered:
        found = features(item.outcome, item.sql)
        key = group_key(found)
        groups.setdefault(key, []).append(item)
        family[key] = (found.outcome, found.tables)

    # Layer 2, per (outcome, tables): union-find over layer 1 groups.
    parent = {key: key for key in groups}

    def root(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    by_family: dict[tuple[str, tuple[str, ...]], list[str]] = defaultdict(list)
    for key in sorted(groups):
        by_family[family[key]].append(key)
    for keys in by_family.values():
        members = [(key, words(item.question)) for key in keys for item in groups[key]]
        for i, (key_a, words_a) in enumerate(members):
            for key_b, words_b in members[i + 1 :]:
                if key_a == key_b or root(key_a) == root(key_b):
                    continue
                if jaccard(words_a, words_b) >= threshold:
                    low, high = sorted((root(key_a), root(key_b)))
                    parent[high] = low
    return {item.id: root(key) for key, members in groups.items() for item in members}


def _recent_cases() -> list[TraceCase]:
    return list(
        TraceCase.objects.order_by("-source_created_at", "-id")[
            : settings.TRACES_CLUSTER_MAX_RUNS
        ]
    )


def assign_clusters() -> int:
    """Store `cluster_key` on the most recent TRACES_CLUSTER_MAX_RUNS cases.
    Returns how many keys changed."""
    cases = _recent_cases()
    keys = cluster(
        (Item(c.pk, c.outcome, c.source_sql, c.question) for c in cases),
        settings.TRACES_CLUSTER_SIMILARITY,
    )
    changed = [c for c in cases if c.cluster_key != keys[c.pk]]
    for c in changed:
        c.cluster_key = keys[c.pk]
    TraceCase.objects.bulk_update(changed, ["cluster_key"], batch_size=500)
    return len(changed)


@dataclass(frozen=True)
class Summary:
    key: str
    label: str
    size: int
    representative_id: int
    member_ids: tuple[int, ...]
    status_counts: dict[str, int]


def label_of(found: Features) -> str:
    """The cluster in words: outcome, tables, shape."""
    tables = ", ".join(found.tables) or "no tables"
    return f"{found.outcome} on {tables}: {describe_shape(found.shape)}"


def describe_shape(shape: str) -> str:
    if shape in (NO_SQL_SHAPE, UNPARSED_SHAPE):
        return "no usable SQL"
    out = []
    for part in shape.split("|"):
        if part.startswith("j") and part[1:].isdigit():
            n = int(part[1:])
            out.append("no join" if n == 0 else f"{n} join{'s' if n > 1 else ''}")
        elif part.startswith("agg:"):
            out.append(part[4:].replace(",", "/"))
        elif part == "group":
            out.append("grouped")
        elif part == "window":
            out.append("window")
        elif part == "nested":
            out.append("subquery or CTE")
        elif part == "topn":
            out.append("top N")
    return ", ".join(out)


def _rank(case: TraceCase) -> tuple[int, datetime, int]:
    """Most signals, then newest, then highest id (so the choice is repeatable)."""
    return (case.signals, case.source_created_at, case.pk)


def summaries() -> list[Summary]:
    """Clusters of the stored `cluster_key`s, largest first (key breaks ties)."""
    by_key: dict[str, list[TraceCase]] = defaultdict(list)
    for case in _recent_cases():
        if case.cluster_key:
            by_key[case.cluster_key].append(case)
    result = []
    for key, members in by_key.items():
        rep = max(members, key=_rank)
        counts: dict[str, int] = defaultdict(int)
        for m in members:
            counts[m.status] += 1
        result.append(
            Summary(
                key=key,
                label=label_of(features(rep.outcome, rep.source_sql)),
                size=len(members),
                representative_id=rep.pk,
                member_ids=tuple(sorted(m.pk for m in members)),
                status_counts=dict(counts),
            )
        )
    return sorted(result, key=lambda s: (-s.size, s.key))
