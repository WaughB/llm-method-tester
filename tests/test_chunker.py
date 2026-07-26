"""Tests for heading-aware document chunking."""

from llm_bench.corpus.documents import Document
from llm_bench.strategies.chunker import chunk_document


def make_doc(text: str) -> Document:
    return Document(doc_id="docs/x.md", title="X", text=text)


class TestChunkDocument:
    def test_splits_on_h2_sections(self) -> None:
        doc = make_doc("# T\n\nintro text\n\n## A\n\nalpha body\n\n## B\n\nbeta body\n")
        chunks = chunk_document(doc, max_words=100, overlap_words=10)
        assert len(chunks) == 3
        assert "intro text" in chunks[0].text
        assert chunks[1].text.startswith("## A")
        assert chunks[2].text.startswith("## B")

    def test_chunk_ids_unique_and_prefixed_with_doc_id(self) -> None:
        doc = make_doc("# T\n\n## A\n\nbody\n\n## B\n\nbody\n")
        chunks = chunk_document(doc, max_words=100, overlap_words=10)
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))
        assert all(i.startswith("docs/x.md#") for i in ids)
        assert all(c.doc_id == "docs/x.md" for c in chunks)

    def test_long_section_windowed_with_overlap(self) -> None:
        words = " ".join(f"w{i}" for i in range(100))
        doc = make_doc(f"# T\n\n## Long\n\n{words}\n")
        chunks = chunk_document(doc, max_words=40, overlap_words=10)
        assert len(chunks) >= 4  # title chunk + >=3 windows of the long section
        # consecutive windows share the overlap region (chunk 0 is the title)
        first_words = chunks[1].text.split()
        second_words = chunks[2].text.split()
        assert first_words[-10:] == second_words[:10]

    def test_all_content_is_covered(self) -> None:
        doc = make_doc("# T\n\nalpha\n\n## S\n\nbravo charlie\n")
        chunks = chunk_document(doc, max_words=100, overlap_words=10)
        combined = " ".join(c.text for c in chunks)
        for token in ("alpha", "bravo", "charlie"):
            assert token in combined

    def test_empty_doc_yields_no_chunks(self) -> None:
        assert chunk_document(make_doc(""), max_words=40, overlap_words=10) == []
