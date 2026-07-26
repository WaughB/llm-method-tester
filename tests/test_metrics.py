"""Tests for the deterministic evaluation metrics."""

from llm_bench.eval.metrics import keyword_recall, retrieval_hit_rate


class TestKeywordRecall:
    def test_full_recall(self) -> None:
        assert keyword_recall("Port 7433 uses glowcast", [["7433"], ["glowcast"]]) == 1.0

    def test_partial_recall(self) -> None:
        assert keyword_recall("Port 7433 only", [["7433"], ["glowcast"]]) == 0.5

    def test_zero_recall(self) -> None:
        assert keyword_recall("no idea", [["7433"], ["glowcast"]]) == 0.0

    def test_alias_group_hits_on_any_alias(self) -> None:
        groups = [["forty-five seconds", "45 seconds", "45s"]]
        assert keyword_recall("The TTL is 45s.", groups) == 1.0

    def test_case_insensitive(self) -> None:
        assert keyword_recall("GLOWCAST protocol", [["glowcast"]]) == 1.0

    def test_whitespace_normalized(self) -> None:
        assert keyword_recall("uses 45\n  seconds total", [["45 seconds"]]) == 1.0

    def test_empty_answer(self) -> None:
        assert keyword_recall("", [["x"]]) == 0.0

    def test_no_groups_returns_zero(self) -> None:
        assert keyword_recall("anything", []) == 0.0


class TestRetrievalHitRate:
    def test_full_hit(self) -> None:
        assert retrieval_hit_rate(["a.md", "b.md"], ["b.md", "a.md", "c.md"]) == 1.0

    def test_partial_hit(self) -> None:
        assert retrieval_hit_rate(["a.md", "b.md"], ["a.md"]) == 0.5

    def test_miss(self) -> None:
        assert retrieval_hit_rate(["a.md"], ["z.md"]) == 0.0

    def test_empty_retrieved(self) -> None:
        assert retrieval_hit_rate(["a.md"], []) == 0.0

    def test_no_gold_sources_returns_none(self) -> None:
        assert retrieval_hit_rate([], ["a.md"]) is None

    def test_duplicates_ignored(self) -> None:
        assert retrieval_hit_rate(["a.md"], ["a.md", "a.md"]) == 1.0
