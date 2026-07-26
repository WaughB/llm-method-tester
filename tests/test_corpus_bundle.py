"""Tests for the combined BenchmarkCorpus bundle."""

from pathlib import Path

from llm_bench.corpus import BenchmarkCorpus


class TestBenchmarkCorpus:
    def test_load_bundles_docs_and_vault(self, mini_corpus_root: Path) -> None:
        corpus = BenchmarkCorpus.load(mini_corpus_root)
        assert len(corpus.documents) == 3
        assert len(corpus.vault) == 4

    def test_content_hash_is_stable(self, mini_corpus_root: Path) -> None:
        a = BenchmarkCorpus.load(mini_corpus_root).content_hash()
        b = BenchmarkCorpus.load(mini_corpus_root).content_hash()
        assert a == b
        assert len(a) == 16

    def test_content_hash_changes_with_content(self, tmp_path: Path) -> None:
        for variant in ("one", "two"):
            (tmp_path / variant / "docs").mkdir(parents=True)
            (tmp_path / variant / "vault").mkdir(parents=True)
            (tmp_path / variant / "docs" / "a.md").write_text(
                f"# A\n\ncontent {variant}", encoding="utf-8"
            )
        h1 = BenchmarkCorpus.load(tmp_path / "one").content_hash()
        h2 = BenchmarkCorpus.load(tmp_path / "two").content_hash()
        assert h1 != h2
