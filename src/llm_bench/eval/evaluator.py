"""Combines deterministic metrics with the LLM judge for one answer."""

from dataclasses import dataclass

from llm_bench.corpus.qa import Question
from llm_bench.eval.judge import JudgeResult, LLMJudge
from llm_bench.eval.metrics import keyword_recall, retrieval_hit_rate


@dataclass(frozen=True)
class EvalOutcome:
    keyword_recall: float
    retrieval_hit_rate: float | None
    judge: JudgeResult | None


class Evaluator:
    def __init__(self, judge: LLMJudge | None) -> None:
        self._judge = judge

    def evaluate(
        self,
        question: Question,
        answer_text: str,
        retrieved_ids: list[str],
        representation: str | None,
    ) -> EvalOutcome:
        if representation == "docs":
            hit_rate = retrieval_hit_rate(question.source_docs, retrieved_ids)
        elif representation == "vault":
            hit_rate = retrieval_hit_rate(question.source_notes, retrieved_ids)
        else:
            hit_rate = None
        judge_result = None
        if self._judge is not None:
            judge_result = self._judge.judge(
                question=question.question,
                gold_answer=question.gold_answer,
                expected_facts=question.expected_keywords,
                candidate=answer_text,
            )
        return EvalOutcome(
            keyword_recall=keyword_recall(answer_text, question.expected_keywords),
            retrieval_hit_rate=hit_rate,
            judge=judge_result,
        )
