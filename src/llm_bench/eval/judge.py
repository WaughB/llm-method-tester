"""Blind LLM-as-judge scoring.

The judge sees only the question, the gold answer, the expected facts, and the
candidate answer — never which model or strategy produced the candidate — to
avoid identity bias (including self-preference, since the judge model is also
one of the benchmarked models).
"""

from dataclasses import dataclass

from llm_bench.llm.base import GenOptions, LLMClient
from llm_bench.llm.jsonutil import extract_json

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 5},
        "verdict": {"type": "string", "enum": ["correct", "partial", "incorrect"]},
        "reasoning": {"type": "string"},
    },
    "required": ["score", "verdict"],
}

_SYSTEM = (
    "You are a strict grader of question-answering systems. Compare the candidate "
    "answer to the gold answer and the expected facts. Score 0-5: 5 = fully correct "
    "and complete, 3 = partially correct, 0 = wrong or unrelated. Penalize invented "
    "facts. Respond only with the requested JSON."
)

_PROMPT_TEMPLATE = """Question:
{question}

Gold answer:
{gold_answer}

Expected facts (each line lists acceptable phrasings of one fact):
{facts}

Candidate answer:
{candidate}

Grade the candidate answer."""


@dataclass(frozen=True)
class JudgeResult:
    score: int
    verdict: str
    reasoning: str


class LLMJudge:
    def __init__(self, client: LLMClient, model: str) -> None:
        self._client = client
        self._model = model

    def judge(
        self,
        question: str,
        gold_answer: str,
        expected_facts: list[list[str]],
        candidate: str,
    ) -> JudgeResult:
        facts = "\n".join("- " + " OR ".join(group) for group in expected_facts)
        prompt = _PROMPT_TEMPLATE.format(
            question=question, gold_answer=gold_answer, facts=facts, candidate=candidate
        )
        try:
            response = self._client.generate(
                self._model,
                prompt,
                system=_SYSTEM,
                json_schema=JUDGE_SCHEMA,
                options=GenOptions(),
            )
        except Exception as exc:  # noqa: BLE001 - a judge failure must never kill a run
            return JudgeResult(score=0, verdict="error", reasoning=str(exc))
        return self._parse(response.text)

    @staticmethod
    def _parse(text: str) -> JudgeResult:
        data = extract_json(text)
        if data is None:
            return JudgeResult(score=0, verdict="unparseable", reasoning=text[:500])
        try:
            score = max(0, min(5, int(data["score"])))
        except (ValueError, KeyError, TypeError):
            return JudgeResult(score=0, verdict="unparseable", reasoning=text[:500])
        return JudgeResult(
            score=score,
            verdict=str(data.get("verdict", "partial")),
            reasoning=str(data.get("reasoning", "")),
        )
