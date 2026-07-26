"""BM25 wrapper and RRF fusion tests."""

from pageindex_test.retrieval.fusion import reciprocal_rank_fusion, top_docs
from pageindex_test.retrieval.lexical import Bm25Index, LexicalHit
from pageindex_test.retrieval.vectors import VectorHit


def chunk(id_: str, doc: str, text: str) -> dict:
    return {"id": id_, "doc_id": doc, "heading_path": "", "text": text}


class TestBm25Index:
    def test_finds_lexical_match(self) -> None:
        # three chunks: rank_bm25 assigns zero idf to terms in exactly half
        # of a corpus, so a 2-chunk fixture would be degenerate
        index = Bm25Index()
        index.rebuild(
            [
                chunk("a#0", "a", "the glowcast gossip protocol"),
                chunk("b#0", "b", "banana smoothie recipes"),
                chunk("c#0", "c", "unrelated filler text entirely"),
            ]
        )
        hits = index.search("glowcast protocol", limit=5)
        assert hits[0].chunk_id == "a#0"
        assert all(h.score > 0 for h in hits)

    def test_empty_index_returns_nothing(self) -> None:
        index = Bm25Index()
        index.rebuild([])
        assert index.search("anything", limit=5) == []

    def test_rebuild_replaces_content(self) -> None:
        index = Bm25Index()
        index.rebuild([chunk("old#0", "old", "obsolete text")])
        index.rebuild(
            [
                chunk("new#0", "new", "fresh text here"),
                chunk("f1#0", "f1", "completely different words"),
                chunk("f2#0", "f2", "another unrelated chunk"),
            ]
        )
        hits = index.search("fresh text", limit=5)
        assert hits[0].chunk_id == "new#0"
        assert all(h.chunk_id != "old#0" for h in hits)


class TestFusion:
    def test_chunks_in_both_lists_rank_first(self) -> None:
        lexical = [LexicalHit("c1", "d1", 9.0), LexicalHit("c2", "d1", 5.0)]
        vector = [VectorHit("c3", "d2", 0.9), VectorHit("c1", "d1", 0.8)]
        fused = reciprocal_rank_fusion(lexical, vector, limit=10)
        assert fused[0].chunk_id == "c1"
        assert fused[0].in_lexical and fused[0].in_vector
        assert {f.chunk_id for f in fused} == {"c1", "c2", "c3"}

    def test_limit_respected(self) -> None:
        lexical = [LexicalHit(f"c{i}", "d", float(10 - i)) for i in range(10)]
        fused = reciprocal_rank_fusion(lexical, [], limit=3)
        assert len(fused) == 3

    def test_top_docs_dedupes_in_rank_order(self) -> None:
        lexical = [
            LexicalHit("c1", "docA", 3.0),
            LexicalHit("c2", "docA", 2.0),
            LexicalHit("c3", "docB", 1.0),
        ]
        fused = reciprocal_rank_fusion(lexical, [], limit=10)
        assert top_docs(fused, 5) == ["docA", "docB"]
        assert top_docs(fused, 1) == ["docA"]
