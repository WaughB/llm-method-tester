"""Deterministic fakes for tests and CI — no model, no network.

FakeLLMClient answers from a script (ordered) or a substring->response map,
recording every call so tests can assert on prompts. FakeEmbeddingClient
hashes tokens into buckets so texts sharing words land near each other in
cosine space, which is enough for retrieval logic to behave plausibly.
"""

import math
from dataclasses import dataclass, field

from llm_bench.llm.base import EmbeddingClient, GenOptions, LLMClient, LLMResponse


@dataclass(frozen=True)
class RecordedCall:
    model: str
    prompt: str
    system: str | None
    json_schema: dict | None


@dataclass
class FakeLLMClient(LLMClient):
    responses: dict[str, str] = field(default_factory=dict)
    script: list[str] = field(default_factory=list)
    default: str = "FAKE ANSWER"
    calls: list[RecordedCall] = field(default_factory=list)

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        json_schema: dict | None = None,
        options: GenOptions | None = None,
    ) -> LLMResponse:
        self.calls.append(RecordedCall(model, prompt, system, json_schema))
        text = self._pick_response(prompt)
        return LLMResponse(
            text=text,
            prompt_tokens=max(1, len(prompt) // 4),
            completion_tokens=max(1, len(text) // 4),
            eval_duration_ns=1_000_000_000,
        )

    def _pick_response(self, prompt: str) -> str:
        if self.script:
            return self.script.pop(0)
        for needle, response in self.responses.items():
            if needle in prompt:
                return response
        return self.default


@dataclass
class FakeEmbeddingClient(EmbeddingClient):
    dim: int = 64

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in text.lower().split():
            # stable across processes (unlike builtin hash with PYTHONHASHSEED)
            bucket = sum(ord(c) * (i + 1) for i, c in enumerate(token)) % self.dim
            vec[bucket] += 1.0
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0.0:
            vec[0] = 1.0
            return vec
        return [x / norm for x in vec]
