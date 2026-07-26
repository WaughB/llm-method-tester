"""Eval runner: execute a gold set through a pipeline variant and score it.

Reuses the benchmark's deterministic keyword metric and blind judge, with the
same deferred-judging pattern (answers first, judging afterward, so the judge
model loads once instead of swapping per question).
"""

import logging

from llm_bench.eval.judge import LLMJudge
from llm_bench.eval.metrics import keyword_recall, retrieval_hit_rate

from pageindex_test.db.repos import EvalRepo

logger = logging.getLogger("pageindex_test.evalmode")


class EvalRunner:
    def __init__(self, repo: EvalRepo, query_pipeline, judge: LLMJudge | None) -> None:
        self._repo = repo
        self._pipeline = query_pipeline
        self._judge = judge

    def run(self, run_id: str) -> None:
        run = self._repo.get_run(run_id)
        if run is None:
            raise KeyError(f"No eval run {run_id}")
        self._repo.start_run(run_id)
        questions = [q for q in self._repo.questions_for(run["set_id"]) if q["approved"]]
        location_id = self._repo.get_set(run["set_id"])["location_id"]
        use_stage = run["pipeline"] == "staged"

        answered: list[tuple[dict, object]] = []
        for question in questions:
            result = self._pipeline.ask(
                location_id,
                question["question"],
                run["model"],
                use_pageindex_stage=use_stage,
            )
            answered.append((question, result))

        for question, result in answered:
            recall = keyword_recall(result.answer, question["expected_keywords"])
            retrieved_docs = list({c.doc_id for c in result.citations})
            hit = retrieval_hit_rate(question["gold_doc_ids"], retrieved_docs)
            judge_score = judge_rationale = None
            if self._judge is not None:
                reference = "; ".join(group[0] for group in question["expected_keywords"])
                verdict = self._judge.judge(
                    question=question["question"],
                    gold_answer=f"A correct answer contains: {reference}",
                    expected_facts=question["expected_keywords"],
                    candidate=result.answer,
                )
                judge_score = verdict.score
                judge_rationale = verdict.reasoning
            self._repo.save_result(
                run_id,
                question_id=question["id"],
                answer=result.answer,
                keyword_recall=recall,
                retrieval_hit=hit,
                judge_score=judge_score,
                judge_rationale=judge_rationale,
                trace_id=result.trace_id,
            )

        summary = self._repo.summarize_run(run_id)
        self._repo.finish_run(run_id, summary)
        logger.info("eval run done", extra={"data": {"run_id": run_id, **summary}})
