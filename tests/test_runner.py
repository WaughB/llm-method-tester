"""End-to-end tests for the benchmark runner, on fakes only."""

import json
from typing import ClassVar

import pytest

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import QADataset, Question
from llm_bench.eval.evaluator import Evaluator
from llm_bench.eval.judge import LLMJudge
from llm_bench.llm.fake import FakeLLMClient
from llm_bench.runner import BenchmarkRunner, RunProgress
from llm_bench.storage.repository import ResultsRepository
from llm_bench.strategies.base import RetrievalStrategy, StrategyAnswer


class StubStrategy(RetrievalStrategy):
    name: ClassVar[str] = "stub"
    representation: ClassVar[str | None] = "docs"

    def __init__(self, answer_text: str = "stub answer") -> None:
        self.answer_text = answer_text
        self.prepare_calls: list[str] = []

    def prepare(self, corpus: BenchmarkCorpus, model: str) -> None:
        self.prepare_calls.append(model)

    def answer(self, question: Question, model: str) -> StrategyAnswer:
        return StrategyAnswer(
            text=self.answer_text,
            retrieved_ids=list(question.source_docs),
            llm_calls=1,
            latency_ms=5.0,
            tokens_per_sec=10.0,
            prompt_tokens=10,
            completion_tokens=5,
            context_chars=100,
        )


class ExplodingStrategy(StubStrategy):
    name: ClassVar[str] = "exploding"

    def answer(self, question: Question, model: str) -> StrategyAnswer:
        raise RuntimeError("strategy blew up")


class FailingPrepareStrategy(StubStrategy):
    name: ClassVar[str] = "failing_prepare"

    def prepare(self, corpus: BenchmarkCorpus, model: str) -> None:
        raise RuntimeError("index build failed")


@pytest.fixture
def dataset(mini_dataset: QADataset) -> QADataset:
    return mini_dataset


@pytest.fixture
def repo() -> ResultsRepository:
    return ResultsRepository(":memory:")


def make_runner(
    repo: ResultsRepository,
    corpus: BenchmarkCorpus,
    dataset: QADataset,
    strategies: list[RetrievalStrategy],
) -> BenchmarkRunner:
    judge_client = FakeLLMClient(
        default=json.dumps({"score": 3, "verdict": "partial", "reasoning": "meh"})
    )
    evaluator = Evaluator(judge=LLMJudge(client=judge_client, model="judge"))
    return BenchmarkRunner(
        repo=repo, corpus=corpus, dataset=dataset, strategies=strategies, evaluator=evaluator
    )


class TestBenchmarkRunner:
    def test_full_matrix_writes_all_rows(
        self, repo: ResultsRepository, mini_corpus: BenchmarkCorpus, dataset: QADataset
    ) -> None:
        runner = make_runner(repo, mini_corpus, dataset, [StubStrategy()])
        run_id = runner.run(models=["m1", "m2"])
        results = repo.results_for_run(run_id)
        assert len(results) == 2 * 1 * 3  # models x strategies x questions
        assert repo.get_run(run_id).status == "completed"
        first = results[0]
        assert first.judge_score == 3
        assert first.keyword_recall >= 0.0
        assert first.retrieval_hit_rate == 1.0  # stub retrieves exactly the gold docs

    def test_model_major_ordering_and_prepare_once_per_model(
        self, repo: ResultsRepository, mini_corpus: BenchmarkCorpus, dataset: QADataset
    ) -> None:
        stub = StubStrategy()
        runner = make_runner(repo, mini_corpus, dataset, [stub])
        run_id = runner.run(models=["m1", "m2"])
        assert stub.prepare_calls == ["m1", "m2"]
        models_in_order = [r.model for r in repo.results_for_run(run_id)]
        assert models_in_order == ["m1"] * 3 + ["m2"] * 3

    def test_per_cell_errors_recorded_not_fatal(
        self, repo: ResultsRepository, mini_corpus: BenchmarkCorpus, dataset: QADataset
    ) -> None:
        runner = make_runner(repo, mini_corpus, dataset, [ExplodingStrategy()])
        run_id = runner.run(models=["m1"])
        results = repo.results_for_run(run_id)
        assert len(results) == 3
        assert all(r.error == "strategy blew up" for r in results)
        assert all(r.judge_score is None for r in results)
        assert repo.get_run(run_id).status == "completed"

    def test_prepare_failure_records_errors_for_all_cells(
        self, repo: ResultsRepository, mini_corpus: BenchmarkCorpus, dataset: QADataset
    ) -> None:
        runner = make_runner(repo, mini_corpus, dataset, [FailingPrepareStrategy()])
        run_id = runner.run(models=["m1"])
        results = repo.results_for_run(run_id)
        assert len(results) == 3
        assert all("index build failed" in (r.error or "") for r in results)

    def test_resume_skips_existing_cells(
        self, repo: ResultsRepository, mini_corpus: BenchmarkCorpus, dataset: QADataset
    ) -> None:
        stub = StubStrategy()
        runner = make_runner(repo, mini_corpus, dataset, [stub])
        run_id = runner.run(models=["m1"], question_ids=["q001"])
        assert len(repo.results_for_run(run_id)) == 1
        # resume the same run with the full question set: only 2 new cells run
        runner.run(models=["m1"], resume_run_id=run_id)
        assert len(repo.results_for_run(run_id)) == 3

    def test_progress_callback(
        self, repo: ResultsRepository, mini_corpus: BenchmarkCorpus, dataset: QADataset
    ) -> None:
        events: list[RunProgress] = []
        runner = make_runner(repo, mini_corpus, dataset, [StubStrategy()])
        runner.run(models=["m1"], progress=events.append)
        assert events[-1].done == events[-1].total == 3
        assert all(e.total == 3 for e in events)

    def test_strategy_filter(
        self, repo: ResultsRepository, mini_corpus: BenchmarkCorpus, dataset: QADataset
    ) -> None:
        runner = make_runner(repo, mini_corpus, dataset, [StubStrategy(), ExplodingStrategy()])
        run_id = runner.run(models=["m1"], strategy_names=["stub"])
        assert {r.strategy for r in repo.results_for_run(run_id)} == {"stub"}

    def test_unknown_strategy_name_raises(
        self, repo: ResultsRepository, mini_corpus: BenchmarkCorpus, dataset: QADataset
    ) -> None:
        runner = make_runner(repo, mini_corpus, dataset, [StubStrategy()])
        with pytest.raises(ValueError, match="nope"):
            runner.run(models=["m1"], strategy_names=["nope"])
