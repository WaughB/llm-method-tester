"""Tests for the vector-RAG strategy on an ephemeral Chroma with fake clients."""

import chromadb
import pytest

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import QADataset
from llm_bench.llm.fake import FakeEmbeddingClient, FakeLLMClient
from llm_bench.strategies.traditional_rag import TraditionalRAGStrategy


@pytest.fixture
def strategy(fake_llm: FakeLLMClient, fake_embedder: FakeEmbeddingClient) -> TraditionalRAGStrategy:
    return TraditionalRAGStrategy(
        llm=fake_llm,
        embedder=fake_embedder,
        chroma_client=chromadb.EphemeralClient(),
        top_k=3,
    )


class TestTraditionalRAG:
    def test_metadata(self) -> None:
        assert TraditionalRAGStrategy.name == "traditional_rag"
        assert TraditionalRAGStrategy.representation == "docs"

    def test_answer_stuffs_retrieved_context_into_prompt(
        self,
        strategy: TraditionalRAGStrategy,
        fake_llm: FakeLLMClient,
        mini_corpus: BenchmarkCorpus,
        mini_dataset: QADataset,
    ) -> None:
        strategy.prepare(mini_corpus, "m")
        question = mini_dataset.get("q001")  # default port -> overview.md

        answer = strategy.answer(question, "m")

        assert answer.llm_calls == 1
        assert answer.context_chars > 0
        assert answer.retrieved_ids
        assert all(rid.startswith("docs/") for rid in answer.retrieved_ids)
        prompt = fake_llm.calls[-1].prompt
        assert question.question in prompt
        # some corpus content made it into the prompt as context
        assert "Widget" in prompt

    def test_retrieval_finds_relevant_doc(
        self,
        strategy: TraditionalRAGStrategy,
        mini_corpus: BenchmarkCorpus,
        mini_dataset: QADataset,
    ) -> None:
        strategy.prepare(mini_corpus, "m")
        # q003 asks about restart downtime, covered only by docs/ops.md
        answer = strategy.answer(mini_dataset.get("q003"), "m")
        assert "docs/ops.md" in answer.retrieved_ids

    def test_prepare_is_idempotent_across_models(
        self,
        strategy: TraditionalRAGStrategy,
        fake_embedder: FakeEmbeddingClient,
        mini_corpus: BenchmarkCorpus,
    ) -> None:
        strategy.prepare(mini_corpus, "m1")
        collection = strategy._collection
        count_after_first = collection.count()
        strategy.prepare(mini_corpus, "m2")  # embedding model unchanged -> no rebuild
        assert strategy._collection.count() == count_after_first
        assert count_after_first > 0

    def test_retrieved_ids_are_deduplicated_doc_ids(
        self,
        strategy: TraditionalRAGStrategy,
        mini_corpus: BenchmarkCorpus,
        mini_dataset: QADataset,
    ) -> None:
        strategy.prepare(mini_corpus, "m")
        answer = strategy.answer(mini_dataset.get("q002"), "m")
        assert len(answer.retrieved_ids) == len(set(answer.retrieved_ids))
