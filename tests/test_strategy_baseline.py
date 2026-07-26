"""Tests for the strategy contract and the no-retrieval baseline."""

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import QADataset
from llm_bench.llm.fake import FakeLLMClient
from llm_bench.strategies.baseline import BaselineStrategy


class TestBaselineStrategy:
    def test_answers_from_model_knowledge_only(
        self, mini_corpus: BenchmarkCorpus, mini_dataset: QADataset
    ) -> None:
        fake = FakeLLMClient(default="The port is 7777.")
        strategy = BaselineStrategy(client=fake)
        strategy.prepare(mini_corpus, "model-x")
        question = mini_dataset.get("q001")

        answer = strategy.answer(question, "model-x")

        assert answer.text == "The port is 7777."
        assert answer.retrieved_ids == []
        assert answer.llm_calls == 1
        assert answer.latency_ms >= 0
        assert answer.context_chars == 0
        # the model gets the question, not corpus content
        assert question.question in fake.calls[0].prompt
        assert fake.calls[0].model == "model-x"

    def test_metadata(self) -> None:
        assert BaselineStrategy.name == "baseline"
        assert BaselineStrategy.representation is None
