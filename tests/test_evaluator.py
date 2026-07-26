"""Tests for the evaluator that combines metrics with the judge."""

import json

from llm_bench.corpus.qa import Question
from llm_bench.eval.evaluator import Evaluator
from llm_bench.eval.judge import LLMJudge
from llm_bench.llm.fake import FakeLLMClient


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


class TestEvaluator:
    def test_docs_representation_scores_against_source_docs(self) -> None:
        outcome = make_evaluator().evaluate(
            make_question(), "It is 7433.", ["docs/config.md"], representation="docs"
        )
        assert outcome.keyword_recall == 1.0
        assert outcome.retrieval_hit_rate == 1.0
        assert outcome.judge is not None
        assert outcome.judge.score == 5

    def test_vault_representation_scores_against_source_notes(self) -> None:
        outcome = make_evaluator().evaluate(
            make_question(), "It is 7433.", ["docs/config.md"], representation="vault"
        )
        # retrieved a doc id, but gold for vault strategies is the note id
        assert outcome.retrieval_hit_rate == 0.0

    def test_no_representation_yields_no_hit_rate(self) -> None:
        outcome = make_evaluator().evaluate(make_question(), "It is 7433.", [], representation=None)
        assert outcome.retrieval_hit_rate is None

    def test_without_judge(self) -> None:
        evaluator = Evaluator(judge=None)
        outcome = evaluator.evaluate(make_question(), "nope", [], representation=None)
        assert outcome.judge is None
        assert outcome.keyword_recall == 0.0
