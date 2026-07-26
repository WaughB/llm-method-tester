"""Combines deterministic metrics with the (deferred) LLM judge."""

from dataclasses import dataclass

from llm_bench.corpus.qa import Question
from llm_bench.eval.judge import JudgeResult, LLMJudge
from llm_bench.eval.metrics import keyword_recall, retrieval_hit_rate
from llm_bench.storage.models import ResultRecord


@dataclass(frozen=True)
class EvalOutcome:
    keyword_recall: float
    retrieval_hit_rate: float | None


class Evaluator:
    def __init__(self, judge: LLMJudge | None) -> None:
        self._judge = judge

    def evaluate_metrics(
        self,
        question: Question,
        answer_text: str,
        retrieved_ids: list[str],
        representation: str | None,
    ) -> EvalOutcome:
        """Deterministic metrics, computed inline with each matrix cell."""
        if representation == "docs":
            hit_rate = retrieval_hit_rate(question.source_docs, retrieved_ids)
        elif representation == "vault":
            hit_rate = retrieval_hit_rate(question.source_notes, retrieved_ids)
        else:
            hit_rate = None
        return EvalOutcome(
            keyword_recall=keyword_recall(answer_text, question.expected_keywords),
            retrieval_hit_rate=hit_rate,
        )

    def judge_answer(self, question: Question, answer_text: str) -> JudgeResult | None:
        """LLM judgment for one answer; None when no judge is configured."""
        if self._judge is None:
            return None
        return self._judge.judge(
            question=question.question,
            gold_answer=question.gold_answer,
            expected_facts=question.expected_keywords,
            candidate=answer_text,
        )

    def judgeable(self, results: list[ResultRecord]) -> list[ResultRecord]:
        """Rows the judge pass should visit (none when judging is disabled)."""
        return results if self._judge is not None else []
