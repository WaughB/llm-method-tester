"""Tests for the LLM client contracts and response value object."""

from llm_bench.llm.base import GenOptions, LLMResponse


class TestLLMResponse:
    def test_tokens_per_sec_computed_from_eval_duration(self) -> None:
        resp = LLMResponse(text="hi", completion_tokens=100, eval_duration_ns=2_000_000_000)
        assert resp.tokens_per_sec == 50.0

    def test_tokens_per_sec_zero_when_no_duration(self) -> None:
        resp = LLMResponse(text="hi", completion_tokens=100, eval_duration_ns=0)
        assert resp.tokens_per_sec == 0.0

    def test_response_is_immutable(self) -> None:
        resp = LLMResponse(text="hi")
        try:
            resp.text = "changed"  # type: ignore[misc]
            raised = False
        except AttributeError:
            raised = True
        assert raised


class TestGenOptions:
    def test_deterministic_defaults(self) -> None:
        opts = GenOptions()
        assert opts.temperature == 0.0
        assert opts.seed == 42
        assert opts.num_ctx == 8192
