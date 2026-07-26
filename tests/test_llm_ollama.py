"""Tests for the Ollama HTTP clients (mocked transport; one live smoke test)."""

import json

import httpx
import pytest

from llm_bench.llm.base import GenOptions
from llm_bench.llm.ollama import OllamaClient, OllamaEmbeddingClient, OllamaError


def make_client(handler) -> OllamaClient:
    return OllamaClient(base_url="http://testserver:11434", transport=httpx.MockTransport(handler))


class TestOllamaClientGenerate:
    def test_sends_expected_payload_and_parses_response(self) -> None:
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "response": "42 is the answer",
                    "prompt_eval_count": 11,
                    "eval_count": 7,
                    "eval_duration": 700_000_000,
                },
            )

        resp = make_client(handler).generate(
            "llama3.1:8b", "the prompt", system="be brief", options=GenOptions(num_ctx=4096)
        )
        assert seen["path"] == "/api/generate"
        payload = seen["payload"]
        assert payload["model"] == "llama3.1:8b"
        assert payload["prompt"] == "the prompt"
        assert payload["system"] == "be brief"
        assert payload["stream"] is False
        assert payload["options"] == {"temperature": 0.0, "seed": 42, "num_ctx": 4096}
        assert payload["keep_alive"] == "10m"
        assert "format" not in payload
        assert resp.text == "42 is the answer"
        assert resp.prompt_tokens == 11
        assert resp.completion_tokens == 7
        assert resp.tokens_per_sec == 10.0

    def test_json_schema_passed_as_format(self) -> None:
        seen: dict = {}
        schema = {"type": "object", "properties": {"score": {"type": "integer"}}}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["payload"] = json.loads(request.content)
            return httpx.Response(200, json={"response": "{}"})

        make_client(handler).generate("m", "p", json_schema=schema)
        assert seen["payload"]["format"] == schema

    def test_model_missing_raises_ollama_error_with_detail(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "model 'nope' not found"})

        with pytest.raises(OllamaError, match="model 'nope' not found"):
            make_client(handler).generate("nope", "p")

    def test_timeout_wrapped_in_ollama_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out")

        with pytest.raises(OllamaError, match="[Tt]im"):
            make_client(handler).generate("m", "p")


class TestOllamaEmbeddingClient:
    def test_embed_batch(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            assert request.url.path == "/api/embed"
            assert payload["model"] == "nomic-embed-text"
            assert payload["input"] == ["a", "b"]
            return httpx.Response(200, json={"embeddings": [[0.1, 0.2], [0.3, 0.4]]})

        client = OllamaEmbeddingClient(
            base_url="http://testserver:11434",
            model="nomic-embed-text",
            transport=httpx.MockTransport(handler),
        )
        assert client.embed(["a", "b"]) == [[0.1, 0.2], [0.3, 0.4]]

    def test_http_error_raises_ollama_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        client = OllamaEmbeddingClient(
            base_url="http://t", model="m", transport=httpx.MockTransport(handler)
        )
        with pytest.raises(OllamaError):
            client.embed(["a"])


@pytest.mark.live
class TestLiveOllama:
    def test_generate_against_local_server(self) -> None:
        client = OllamaClient(base_url="http://localhost:11434")
        resp = client.generate("llama3.1:8b", "Reply with exactly the word OK.")
        assert resp.text.strip() != ""
        assert resp.completion_tokens > 0
