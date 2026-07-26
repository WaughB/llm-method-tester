"""The strategy contract every retrieval approach implements."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import Question

ANSWER_SYSTEM = (
    "You are a precise technical assistant. Answer the question concisely and "
    "factually. If context is provided, answer strictly from it."
)


@dataclass(frozen=True)
class StrategyAnswer:
    """One strategy's answer to one question, with cost accounting."""

    text: str
    retrieved_ids: list[str] = field(default_factory=list)  # doc/note ids handed to the model
    llm_calls: int = 1
    latency_ms: float = 0.0
    tokens_per_sec: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    context_chars: int = 0


class RetrievalStrategy(ABC):
    """A way of answering questions, with or without retrieval.

    `representation` declares which corpus half the strategy retrieves from,
    so the evaluator knows which gold sources to score hit-rate against:
    "docs" (plain documents), "vault" (Obsidian notes), or None (no retrieval).
    """

    name: ClassVar[str]
    representation: ClassVar[str | None]

    @abstractmethod
    def prepare(self, corpus: BenchmarkCorpus, model: str) -> None:
        """Build or load any index needed before answering. Called once per model."""

    @abstractmethod
    def answer(self, question: Question, model: str) -> StrategyAnswer:
        """Answer one question using `model`."""
