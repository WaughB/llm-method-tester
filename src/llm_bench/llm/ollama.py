"""Ollama HTTP clients for generation and embeddings."""

import httpx

from llm_bench.llm.base import EmbeddingClient, GenOptions, LLMClient, LLMResponse

DEFAULT_KEEP_ALIVE = "10m"


class OllamaError(RuntimeError):
    """Raised for any transport or API failure talking to Ollama."""


def _error_detail(response: httpx.Response) -> str:
    try:
        return response.json().get("error", response.text)
    except ValueError:
        return response.text


class OllamaClient(LLMClient):
    def __init__(
        self,
        base_url: str,
        *,
        timeout_s: float = 600.0,
        keep_alive: str = DEFAULT_KEEP_ALIVE,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._keep_alive = keep_alive
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s, transport=transport)

    def generate(
        self,
        model: str,
        prompt: str,
        *,
        system: str | None = None,
        json_schema: dict | None = None,
        options: GenOptions | None = None,
    ) -> LLMResponse:
        opts = options or GenOptions()
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self._keep_alive,
            "options": {
                "temperature": opts.temperature,
                "seed": opts.seed,
                "num_ctx": opts.num_ctx,
            },
        }
        if system is not None:
            payload["system"] = system
        if json_schema is not None:
            payload["format"] = json_schema
        data = self._post("/api/generate", payload)
        return LLMResponse(
            text=data.get("response", ""),
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
            eval_duration_ns=data.get("eval_duration", 0),
        )

    def _post(self, path: str, payload: dict) -> dict:
        try:
            response = self._client.post(path, json=payload)
        except httpx.TimeoutException as exc:
            raise OllamaError(f"Timeout calling Ollama {path}: {exc}") from exc
        except httpx.HTTPError as exc:
            raise OllamaError(f"HTTP error calling Ollama {path}: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(
                f"Ollama {path} returned {response.status_code}: {_error_detail(response)}"
            )
        return response.json()


class OllamaEmbeddingClient(EmbeddingClient):
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout_s: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._model = model
        self._client = httpx.Client(base_url=base_url, timeout=timeout_s, transport=transport)

    def embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self._client.post("/api/embed", json={"model": self._model, "input": texts})
        except httpx.HTTPError as exc:
            raise OllamaError(f"HTTP error calling Ollama /api/embed: {exc}") from exc
        if response.status_code != 200:
            raise OllamaError(
                f"Ollama /api/embed returned {response.status_code}: {_error_detail(response)}"
            )
        return response.json()["embeddings"]
