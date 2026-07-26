"""Tests for the SQLite results repository."""

from pathlib import Path

import pytest

from llm_bench.storage.models import ResultRecord
from llm_bench.storage.repository import ResultsRepository


@pytest.fixture
def repo() -> ResultsRepository:
    return ResultsRepository(":memory:")


def make_result(
    run_id: int,
    model: str = "model-a",
    strategy: str = "baseline",
    question_id: str = "q001",
    **overrides,
) -> ResultRecord:
    defaults = dict(
        run_id=run_id,
        model=model,
        strategy=strategy,
        question_id=question_id,
        category="single_hop",
        answer="an answer",
        retrieved_ids=["docs/a.md"],
        latency_ms=120.5,
        tokens_per_sec=42.0,
        llm_calls=1,
        prompt_tokens=100,
        completion_tokens=20,
        context_chars=500,
        keyword_recall=0.5,
        retrieval_hit_rate=1.0,
        judge_score=4,
        judge_verdict="correct",
        judge_reasoning="looks right",
        error=None,
    )
    defaults.update(overrides)
    return ResultRecord(**defaults)


class TestRuns:
    def test_create_and_get_run(self, repo: ResultsRepository) -> None:
        run_id = repo.create_run({"models": ["m1"], "strategies": ["baseline"]})
        run = repo.get_run(run_id)
        assert run.id == run_id
        assert run.status == "running"
        assert run.config == {"models": ["m1"], "strategies": ["baseline"]}
        assert run.started_at  # ISO timestamp set

    def test_finish_run(self, repo: ResultsRepository) -> None:
        run_id = repo.create_run({})
        repo.finish_run(run_id, "completed")
        run = repo.get_run(run_id)
        assert run.status == "completed"
        assert run.finished_at

    def test_finish_run_with_error(self, repo: ResultsRepository) -> None:
        run_id = repo.create_run({})
        repo.finish_run(run_id, "failed", error="corpus missing")
        assert repo.get_run(run_id).error == "corpus missing"

    def test_list_runs_newest_first(self, repo: ResultsRepository) -> None:
        first = repo.create_run({})
        second = repo.create_run({})
        assert [r.id for r in repo.list_runs()] == [second, first]

    def test_get_unknown_run_raises(self, repo: ResultsRepository) -> None:
        with pytest.raises(KeyError):
            repo.get_run(999)


class TestResults:
    def test_save_and_read_roundtrip(self, repo: ResultsRepository) -> None:
        run_id = repo.create_run({})
        repo.save_result(make_result(run_id))
        [result] = repo.results_for_run(run_id)
        assert result.model == "model-a"
        assert result.retrieved_ids == ["docs/a.md"]
        assert result.keyword_recall == 0.5
        assert result.judge_score == 4

    def test_nullable_fields_roundtrip(self, repo: ResultsRepository) -> None:
        run_id = repo.create_run({})
        repo.save_result(
            make_result(
                run_id,
                retrieval_hit_rate=None,
                judge_score=None,
                judge_verdict=None,
                judge_reasoning=None,
                error="model blew up",
            )
        )
        [result] = repo.results_for_run(run_id)
        assert result.retrieval_hit_rate is None
        assert result.judge_score is None
        assert result.error == "model blew up"

    def test_existing_cells_supports_resume(self, repo: ResultsRepository) -> None:
        run_id = repo.create_run({})
        repo.save_result(make_result(run_id, model="m1", strategy="s1", question_id="q1"))
        repo.save_result(make_result(run_id, model="m1", strategy="s1", question_id="q2"))
        assert repo.existing_cells(run_id) == {("m1", "s1", "q1"), ("m1", "s1", "q2")}

    def test_persists_to_file(self, tmp_path: Path) -> None:
        db = tmp_path / "results.db"
        repo1 = ResultsRepository(db)
        run_id = repo1.create_run({})
        repo1.save_result(make_result(run_id))
        repo1.close()
        repo2 = ResultsRepository(db)
        assert len(repo2.results_for_run(run_id)) == 1


class TestSummary:
    def test_aggregates_per_model_strategy(self, repo: ResultsRepository) -> None:
        run_id = repo.create_run({})
        repo.save_result(
            make_result(run_id, model="m1", strategy="s1", question_id="q1", judge_score=4)
        )
        repo.save_result(
            make_result(run_id, model="m1", strategy="s1", question_id="q2", judge_score=2)
        )
        repo.save_result(
            make_result(
                run_id,
                model="m1",
                strategy="s2",
                question_id="q1",
                judge_score=5,
                retrieval_hit_rate=None,
            )
        )
        summary = repo.summary_for_run(run_id)
        by_key = {(row.model, row.strategy): row for row in summary}
        assert by_key[("m1", "s1")].avg_judge_score == 3.0
        assert by_key[("m1", "s1")].count == 2
        assert by_key[("m1", "s2")].avg_retrieval_hit_rate is None

    def test_category_breakdown(self, repo: ResultsRepository) -> None:
        run_id = repo.create_run({})
        repo.save_result(make_result(run_id, question_id="q1", category="multi_hop", judge_score=4))
        repo.save_result(
            make_result(run_id, question_id="q2", category="single_hop", judge_score=2)
        )
        summary = repo.summary_for_run(run_id, category="multi_hop")
        assert len(summary) == 1
        assert summary[0].avg_judge_score == 4.0

    def test_errors_counted(self, repo: ResultsRepository) -> None:
        run_id = repo.create_run({})
        repo.save_result(make_result(run_id, question_id="q1"))
        repo.save_result(make_result(run_id, question_id="q2", error="boom", judge_score=None))
        summary = repo.summary_for_run(run_id)
        assert summary[0].error_count == 1
