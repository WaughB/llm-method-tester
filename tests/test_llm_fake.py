"""Tests for the fake LLM/embedding clients used across the test suite and CI."""

import math

from llm_bench.llm.fake import FakeEmbeddingClient, FakeLLMClient


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


class TestFakeLLMClient:
    def test_returns_default_response(self) -> None:
        fake = FakeLLMClient(default="canned answer")
        resp = fake.generate("model-a", "What is the capital of France?")
        assert resp.text == "canned answer"

    def test_records_calls_with_all_arguments(self) -> None:
        fake = FakeLLMClient()
        fake.generate("model-a", "prompt one", system="sys", json_schema={"type": "object"})
        assert len(fake.calls) == 1
        call = fake.calls[0]
        assert call.model == "model-a"
        assert call.prompt == "prompt one"
        assert call.system == "sys"
        assert call.json_schema == {"type": "object"}

    def test_substring_matching_picks_mapped_response(self) -> None:
        fake = FakeLLMClient(responses={"lease TTL": "The TTL is 30 seconds."})
        resp = fake.generate("m", "Question about the lease TTL please")
        assert resp.text == "The TTL is 30 seconds."

    def test_script_returns_responses_in_order(self) -> None:
        fake = FakeLLMClient(script=["first", "second"])
        assert fake.generate("m", "a").text == "first"
        assert fake.generate("m", "b").text == "second"
        # script exhausted -> falls back to default
        assert fake.generate("m", "c").text == fake.default

    def test_response_has_plausible_token_accounting(self) -> None:
        fake = FakeLLMClient(default="four words long answer")
        resp = fake.generate("m", "some prompt")
        assert resp.prompt_tokens > 0
        assert resp.completion_tokens > 0
        assert resp.tokens_per_sec > 0


class TestFakeEmbeddingClient:
    def test_deterministic(self) -> None:
        fake = FakeEmbeddingClient()
        assert fake.embed(["hello world"]) == fake.embed(["hello world"])

    def test_dimension_and_batch(self) -> None:
        fake = FakeEmbeddingClient(dim=16)
        vecs = fake.embed(["a", "b", "c"])
        assert len(vecs) == 3
        assert all(len(v) == 16 for v in vecs)

    def test_similar_texts_are_closer_than_dissimilar(self) -> None:
        fake = FakeEmbeddingClient()
        [query, similar, unrelated] = fake.embed(
            [
                "lease TTL configuration seconds",
                "the lease TTL is configured in seconds",
                "banana smoothie recipe blender",
            ]
        )
        assert cosine(query, similar) > cosine(query, unrelated)

    def test_vectors_are_normalized(self) -> None:
        fake = FakeEmbeddingClient()
        [vec] = fake.embed(["normalize me"])
        norm = math.sqrt(sum(x * x for x in vec))
        assert abs(norm - 1.0) < 1e-9
