"""Tests for the Obsidian-style RAG strategy (BM25 seeds + link-graph expansion)."""

import pytest

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import QADataset
from llm_bench.llm.fake import FakeLLMClient
from llm_bench.strategies.obsidian_rag import ObsidianRAGStrategy


@pytest.fixture
def strategy(fake_llm: FakeLLMClient) -> ObsidianRAGStrategy:
    return ObsidianRAGStrategy(llm=fake_llm, seed_k=2, max_notes=3)


class TestObsidianRAG:
    def test_metadata(self) -> None:
        assert ObsidianRAGStrategy.name == "obsidian_rag"
        assert ObsidianRAGStrategy.representation == "vault"

    def test_bm25_seed_finds_lexically_relevant_note(
        self,
        strategy: ObsidianRAGStrategy,
        mini_corpus: BenchmarkCorpus,
        mini_dataset: QADataset,
    ) -> None:
        strategy.prepare(mini_corpus, "m")
        # q003: "How long is restart downtime?" -> Runbooks/Restart.md
        answer = strategy.answer(mini_dataset.get("q003"), "m")
        assert "vault/Runbooks/Restart.md" in answer.retrieved_ids

    def test_graph_expansion_pulls_linked_notes(
        self,
        strategy: ObsidianRAGStrategy,
        mini_corpus: BenchmarkCorpus,
        mini_dataset: QADataset,
    ) -> None:
        strategy.prepare(mini_corpus, "m")
        # q002 needs Rate Limits (lexical hit) AND Gizmo (reachable via link graph)
        answer = strategy.answer(mini_dataset.get("q002"), "m")
        assert "vault/Reference/Rate Limits.md" in answer.retrieved_ids
        assert "vault/Concepts/Gizmo.md" in answer.retrieved_ids

    def test_respects_max_notes_cap(
        self,
        mini_corpus: BenchmarkCorpus,
        mini_dataset: QADataset,
        fake_llm: FakeLLMClient,
    ) -> None:
        strategy = ObsidianRAGStrategy(llm=fake_llm, seed_k=3, max_notes=2)
        strategy.prepare(mini_corpus, "m")
        answer = strategy.answer(mini_dataset.get("q002"), "m")
        assert len(answer.retrieved_ids) <= 2

    def test_context_contains_note_titles_and_folders(
        self,
        strategy: ObsidianRAGStrategy,
        fake_llm: FakeLLMClient,
        mini_corpus: BenchmarkCorpus,
        mini_dataset: QADataset,
    ) -> None:
        strategy.prepare(mini_corpus, "m")
        strategy.answer(mini_dataset.get("q003"), "m")
        prompt = fake_llm.calls[-1].prompt
        assert "Restart" in prompt
        assert "Runbooks" in prompt
        assert "widget restart" in prompt  # note body made it in

    def test_single_llm_call_and_accounting(
        self,
        strategy: ObsidianRAGStrategy,
        mini_corpus: BenchmarkCorpus,
        mini_dataset: QADataset,
    ) -> None:
        strategy.prepare(mini_corpus, "m")
        answer = strategy.answer(mini_dataset.get("q001"), "m")
        assert answer.llm_calls == 1
        assert answer.context_chars > 0
        assert answer.latency_ms >= 0

    def test_deterministic_retrieval(
        self,
        strategy: ObsidianRAGStrategy,
        mini_corpus: BenchmarkCorpus,
        mini_dataset: QADataset,
    ) -> None:
        strategy.prepare(mini_corpus, "m")
        a = strategy.answer(mini_dataset.get("q002"), "m")
        b = strategy.answer(mini_dataset.get("q002"), "m")
        assert a.retrieved_ids == b.retrieved_ids
