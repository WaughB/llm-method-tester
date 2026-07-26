"""Abstract contracts for text generation and embeddings.

Every component that talks to a model depends on these ABCs, never on a
concrete client, so the whole benchmark can run against fakes in CI.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class GenOptions:
    """Generation options; defaults are pinned for reproducible benchmarks."""

    temperature: float = 0.0
    seed: int = 42
    num_ctx: int = 8192


@dataclass(frozen=True)
class LLMResponse:
    """A single generation result plus the token accounting needed for metrics."""

    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    eval_duration_ns: int = 0

    @property
    def tokens_per_sec(self) -> float:
        if self.eval_duration_ns <= 0:
            return 0.0
        return self.completion_tokens / (self.eval_duration_ns / 1_000_000_000)


class LLMClient(ABC):
    """Text-generation client contract."""

    @abstractmethod
    def generate(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        json_schema: dict | None = None,
        options: GenOptions | None = None,
    ) -> LLMResponse:
        """Generate a completion. `json_schema` forces structured JSON output."""


class EmbeddingClient(ABC):
    """Embedding client contract."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into vectors."""
