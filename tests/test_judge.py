"""Tests for the blind LLM judge."""

import json

from llm_bench.eval.judge import JUDGE_SCHEMA, LLMJudge
from llm_bench.llm.fake import FakeLLMClient


def make_judge(fake: FakeLLMClient) -> LLMJudge:
    return LLMJudge(client=fake, model="judge-model")


class TestLLMJudge:
    def test_parses_structured_verdict(self) -> None:
        fake = FakeLLMClient(
            default=json.dumps(
                {"score": 4, "verdict": "correct", "reasoning": "matches the gold answer"}
            )
        )
        result = make_judge(fake).judge(
            question="What is the port?",
            gold_answer="7433",
            expected_facts=[["7433"]],
            candidate="It is 7433.",
        )
        assert result.score == 4
        assert result.verdict == "correct"
        assert result.reasoning == "matches the gold answer"

    def test_requests_json_schema_output(self) -> None:
        fake = FakeLLMClient(default=json.dumps({"score": 0, "verdict": "incorrect"}))
        make_judge(fake).judge("q", "gold", [["f"]], "cand")
        assert fake.calls[0].json_schema == JUDGE_SCHEMA
        assert fake.calls[0].model == "judge-model"

    def test_prompt_is_blind_but_complete(self) -> None:
        fake = FakeLLMClient(default=json.dumps({"score": 5, "verdict": "correct"}))
        make_judge(fake).judge(
            question="What is the port?",
            gold_answer="7433 is the port",
            expected_facts=[["7433"]],
            candidate="candidate answer text",
        )
        prompt = fake.calls[0].prompt
        assert "What is the port?" in prompt
        assert "7433 is the port" in prompt
        assert "candidate answer text" in prompt
        # blind: no model or strategy identity leaks into the judge prompt
        assert "gpt-oss" not in prompt
        assert "strategy" not in prompt.lower()

    def test_malformed_json_falls_back(self) -> None:
        fake = FakeLLMClient(default="I think the answer is pretty good!")
        result = make_judge(fake).judge("q", "gold", [["f"]], "cand")
        assert result.score == 0
        assert result.verdict == "unparseable"

    def test_score_clamped_to_range(self) -> None:
        fake = FakeLLMClient(default=json.dumps({"score": 99, "verdict": "correct"}))
        result = make_judge(fake).judge("q", "gold", [["f"]], "cand")
        assert result.score == 5

    def test_llm_error_falls_back_to_error_verdict(self) -> None:
        class ExplodingClient(FakeLLMClient):
            def generate(self, *args, **kwargs):  # type: ignore[override]
                raise RuntimeError("ollama down")

        result = make_judge(ExplodingClient()).judge("q", "gold", [["f"]], "cand")
        assert result.score == 0
        assert result.verdict == "error"
        assert "ollama down" in result.reasoning
