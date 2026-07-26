"""Baseline: the model answers from its own knowledge — the control condition.

On a fictional corpus this should score near zero, proving the other
strategies' gains come from retrieval rather than pretraining.
"""

import time
from typing import ClassVar

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import Question
from llm_bench.llm.base import GenOptions, LLMClient
from llm_bench.strategies.base import RetrievalStrategy, StrategyAnswer

_SYSTEM = (
    "You are a precise technical assistant. Answer the question concisely "
    "from your own knowledge. If you do not know, say so."
)


class BaselineStrategy(RetrievalStrategy):
    name: ClassVar[str] = "baseline"
    representation: ClassVar[str | None] = None

    def __init__(self, client: LLMClient, options: GenOptions | None = None) -> None:
        self._client = client
        self._options = options or GenOptions()

    def prepare(self, corpus: BenchmarkCorpus, model: str) -> None:
        pass  # nothing to index

    def answer(self, question: Question, model: str) -> StrategyAnswer:
        start = time.perf_counter()
        response = self._client.generate(
            model, question.question, system=_SYSTEM, options=self._options
        )
        latency_ms = (time.perf_counter() - start) * 1000
        return StrategyAnswer(
            text=response.text,
            retrieved_ids=[],
            llm_calls=1,
            latency_ms=latency_ms,
            tokens_per_sec=response.tokens_per_sec,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            context_chars=0,
        )
