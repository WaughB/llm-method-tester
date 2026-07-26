"""Deterministic, reproducible answer/retrieval metrics."""

import re

_WS_RE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", text.lower()).strip()


def keyword_recall(answer: str, expected_keywords: list[list[str]]) -> float:
    """Fraction of alias groups with at least one alias present in the answer.

    A group like ["45 seconds", "45s"] is hit if ANY alias appears
    (case-insensitive, whitespace-normalized substring match).
    """
    if not expected_keywords:
        return 0.0
    haystack = _normalize(answer)
    hits = sum(
        1 for group in expected_keywords if any(_normalize(alias) in haystack for alias in group)
    )
    return hits / len(expected_keywords)


def retrieval_hit_rate(gold_sources: list[str], retrieved: list[str]) -> float | None:
    """Fraction of gold sources present in the retrieved set.

    Returns None when there are no gold sources to score against
    (e.g. the baseline strategy, which retrieves nothing by design).
    """
    gold = set(gold_sources)
    if not gold:
        return None
    return len(gold & set(retrieved)) / len(gold)
