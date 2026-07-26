"""Validation of the committed Aurora Mesh benchmark corpus.

These tests enforce internal consistency: every wikilink resolves, every gold
source exists, every expected keyword is actually findable in its sources, and
the committed corpus matches what the generator produces (drift guard).
"""

from pathlib import Path

import pytest

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import QADataset
from llm_bench.corpus_gen import generate

CORPUS_ROOT = Path(__file__).parent.parent / "corpus"


@pytest.fixture(scope="module")
def corpus() -> BenchmarkCorpus:
    return BenchmarkCorpus.load(CORPUS_ROOT)


@pytest.fixture(scope="module")
def dataset() -> QADataset:
    return QADataset.load(CORPUS_ROOT / "qa" / "questions.json")


class TestCorpusShape:
    def test_minimum_sizes(self, corpus: BenchmarkCorpus, dataset: QADataset) -> None:
        assert len(corpus.documents) >= 10
        assert len(corpus.vault) >= 20
        assert len(dataset) >= 30

    def test_all_wikilinks_resolve(self, corpus: BenchmarkCorpus) -> None:
        assert corpus.vault.unresolved_links == set()

    def test_vault_uses_folders(self, corpus: BenchmarkCorpus) -> None:
        folders = {note.folder for note in corpus.vault}
        assert len(folders - {""}) >= 3

    def test_vault_notes_are_tagged_and_linked(self, corpus: BenchmarkCorpus) -> None:
        tagged = sum(1 for n in corpus.vault if n.tags)
        linked = sum(1 for n in corpus.vault if corpus.vault.outlinks(n.note_id))
        assert tagged >= len(corpus.vault) // 2
        assert linked >= len(corpus.vault) // 2

    def test_docs_have_heading_structure(self, corpus: BenchmarkCorpus) -> None:
        # PageIndex needs a real heading hierarchy to build trees from
        with_subheadings = sum(1 for d in corpus.documents if "\n## " in d.text)
        assert with_subheadings >= len(corpus.documents) - 1


class TestQuestionConsistency:
    def test_all_categories_represented(self, dataset: QADataset) -> None:
        categories = {q.category for q in dataset}
        assert categories == {"single_hop", "multi_hop", "aggregation"}

    def test_every_question_has_sources(self, dataset: QADataset) -> None:
        for q in dataset:
            assert q.source_docs, f"{q.id} has no source docs"
            assert q.source_notes, f"{q.id} has no source notes"

    def test_gold_sources_exist(self, corpus: BenchmarkCorpus, dataset: QADataset) -> None:
        doc_ids = {d.doc_id for d in corpus.documents}
        note_ids = {n.note_id for n in corpus.vault}
        for q in dataset:
            for doc_id in q.source_docs:
                assert doc_id in doc_ids, f"{q.id}: unknown source doc {doc_id}"
            for note_id in q.source_notes:
                assert note_id in note_ids, f"{q.id}: unknown source note {note_id}"

    def test_keywords_findable_in_source_docs(
        self, corpus: BenchmarkCorpus, dataset: QADataset
    ) -> None:
        for q in dataset:
            haystack = " ".join(corpus.documents.get(d).text for d in q.source_docs).lower()
            for group in q.expected_keywords:
                assert any(alias.lower() in haystack for alias in group), (
                    f"{q.id}: no alias of {group} found in source docs"
                )

    def test_keywords_findable_in_source_notes(
        self, corpus: BenchmarkCorpus, dataset: QADataset
    ) -> None:
        for q in dataset:
            haystack = " ".join(corpus.vault.get(n).body for n in q.source_notes).lower()
            for group in q.expected_keywords:
                assert any(alias.lower() in haystack for alias in group), (
                    f"{q.id}: no alias of {group} found in source notes"
                )

    def test_gold_answer_contains_at_least_one_keyword_group(self, dataset: QADataset) -> None:
        for q in dataset:
            answer = q.gold_answer.lower()
            hits = sum(
                1 for group in q.expected_keywords if any(a.lower() in answer for a in group)
            )
            assert hits >= 1, f"{q.id}: gold answer contains no expected keyword"


class TestDriftGuard:
    def test_committed_corpus_matches_generator(self, tmp_path: Path) -> None:
        generate(tmp_path)
        generated = {
            p.relative_to(tmp_path).as_posix(): p.read_text(encoding="utf-8")
            for p in tmp_path.rglob("*")
            if p.is_file()
        }
        committed = {
            p.relative_to(CORPUS_ROOT).as_posix(): p.read_text(encoding="utf-8")
            for p in CORPUS_ROOT.rglob("*")
            if p.is_file()
        }
        assert generated.keys() == committed.keys()
        for name in generated:
            assert generated[name] == committed[name], f"drift in {name}"
