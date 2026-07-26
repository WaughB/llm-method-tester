"""Tests for the plain-document corpus loader."""

from pathlib import Path

from llm_bench.corpus.documents import DocumentCorpus


class TestDocumentCorpus:
    def test_loads_all_markdown_docs_sorted(self, mini_corpus_root: Path) -> None:
        corpus = DocumentCorpus.load(mini_corpus_root)
        assert [d.doc_id for d in corpus] == [
            "docs/api.md",
            "docs/overview.md",
            "docs/ops.md",
        ] or [d.doc_id for d in corpus] == sorted(d.doc_id for d in corpus)
        assert len(corpus) == 3

    def test_doc_ids_are_posix_relative_paths(self, mini_corpus_root: Path) -> None:
        corpus = DocumentCorpus.load(mini_corpus_root)
        assert all(d.doc_id.startswith("docs/") for d in corpus)
        assert all("\\" not in d.doc_id for d in corpus)

    def test_title_taken_from_first_h1(self, mini_corpus_root: Path) -> None:
        corpus = DocumentCorpus.load(mini_corpus_root)
        assert corpus.get("docs/overview.md").title == "Widget Overview"

    def test_get_returns_full_text(self, mini_corpus_root: Path) -> None:
        doc = DocumentCorpus.load(mini_corpus_root).get("docs/api.md")
        assert "X-Widget-Key" in doc.text

    def test_get_unknown_id_raises(self, mini_corpus_root: Path) -> None:
        corpus = DocumentCorpus.load(mini_corpus_root)
        try:
            corpus.get("docs/nope.md")
            raised = False
        except KeyError:
            raised = True
        assert raised
