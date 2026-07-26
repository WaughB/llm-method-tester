"""Tests for the evaluator that combines metrics with the deferred judge."""

import json

from llm_bench.corpus.qa import Question
from llm_bench.eval.evaluator import Evaluator
from llm_bench.eval.judge import LLMJudge
from llm_bench.llm.fake import FakeLLMClient
from llm_bench.storage.models import ResultRecord


def make_question() -> Question:
    return Question(
        id="q1",
        question="What is the port?",
        category="single_hop",
        expected_keywords=[["7433"]],
        source_docs=["docs/config.md"],
        source_notes=["vault/Reference/Ports.md"],
        gold_answer="The port is 7433.",
    )


def make_evaluator() -> Evaluator:
    fake = FakeLLMClient(default=json.dumps({"score": 5, "verdict": "correct", "reasoning": "ok"}))
    return Evaluator(judge=LLMJudge(client=fake, model="j"))


def make_result() -> ResultRecord:
    return ResultRecord(
        id=1,
        run_id=1,
        model="m",
        strategy="s",
        question_id="q1",
        category="single_hop",
        answer="It is 7433.",
        retrieved_ids=[],
        latency_ms=1.0,
        tokens_per_sec=1.0,
        llm_calls=1,
        prompt_tokens=1,
        completion_tokens=1,
        context_chars=0,
        keyword_recall=1.0,
    )


class TestEvaluateMetrics:
    def test_docs_representation_scores_against_source_docs(self) -> None:
        outcome = make_evaluator().evaluate_metrics(
            make_question(), "It is 7433.", ["docs/config.md"], representation="docs"
        )
        assert outcome.keyword_recall == 1.0
        assert outcome.retrieval_hit_rate == 1.0

    def test_vault_representation_scores_against_source_notes(self) -> None:
        outcome = make_evaluator().evaluate_metrics(
            make_question(), "It is 7433.", ["docs/config.md"], representation="vault"
        )
        # retrieved a doc id, but gold for vault strategies is the note id
        assert outcome.retrieval_hit_rate == 0.0

    def test_no_representation_yields_no_hit_rate(self) -> None:
        outcome = make_evaluator().evaluate_metrics(
            make_question(), "It is 7433.", [], representation=None
        )
        assert outcome.retrieval_hit_rate is None


class TestJudging:
    def test_judge_answer_returns_verdict(self) -> None:
        result = make_evaluator().judge_answer(make_question(), "It is 7433.")
        assert result is not None
        assert result.score == 5

    def test_judge_answer_none_without_judge(self) -> None:
        evaluator = Evaluator(judge=None)
        assert evaluator.judge_answer(make_question(), "nope") is None

    def test_judgeable_passthrough_with_judge(self) -> None:
        rows = [make_result()]
        assert make_evaluator().judgeable(rows) == rows

    def test_judgeable_empty_without_judge(self) -> None:
        assert Evaluator(judge=None).judgeable([make_result()]) == []
