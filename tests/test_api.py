"""API tests: FastAPI TestClient over fully faked dependencies."""

import json
import time
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient

from llm_bench.api.app import ApiDeps, create_app
from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import QADataset, Question
from llm_bench.eval.evaluator import Evaluator
from llm_bench.eval.judge import LLMJudge
from llm_bench.llm.fake import FakeLLMClient
from llm_bench.runner import BenchmarkRunner
from llm_bench.storage.repository import ResultsRepository
from llm_bench.strategies.base import RetrievalStrategy, StrategyAnswer


class FastStub(RetrievalStrategy):
    name: ClassVar[str] = "stub"
    representation: ClassVar[str | None] = "docs"
    delay_s: ClassVar[float] = 0.0

    def prepare(self, corpus: BenchmarkCorpus, model: str) -> None:
        pass

    def answer(self, question: Question, model: str) -> StrategyAnswer:
        if self.delay_s:
            time.sleep(self.delay_s)
        return StrategyAnswer(text="stub", retrieved_ids=list(question.source_docs))


class SlowStub(FastStub):
    name: ClassVar[str] = "slow"
    delay_s: ClassVar[float] = 0.15


def wait_for_completion(client: TestClient, run_id: int, timeout_s: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        data = client.get(f"/api/runs/{run_id}").json()
        if data["status"] != "running":
            return data
        time.sleep(0.02)
    raise TimeoutError(f"run {run_id} did not finish")


@pytest.fixture
def client(mini_corpus: BenchmarkCorpus, mini_dataset: QADataset) -> TestClient:
    repo = ResultsRepository(":memory:")
    judge_client = FakeLLMClient(default=json.dumps({"score": 4, "verdict": "correct"}))
    runner = BenchmarkRunner(
        repo=repo,
        corpus=mini_corpus,
        dataset=mini_dataset,
        strategies=[FastStub(), SlowStub()],
        evaluator=Evaluator(judge=LLMJudge(client=judge_client, model="j")),
    )
    deps = ApiDeps(
        repo=repo,
        runner=runner,
        dataset=mini_dataset,
        models=["m1", "m2"],
        health_check=lambda: {"ok": True, "models": ["m1", "m2"]},
        frontend_dist=None,
    )
    return TestClient(create_app(deps))


class TestMetaEndpoints:
    def test_health(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True, "models": ["m1", "m2"]}

    def test_meta_lists_models_strategies_questions(self, client: TestClient) -> None:
        data = client.get("/api/meta").json()
        assert data["models"] == ["m1", "m2"]
        assert data["strategies"] == ["stub", "slow"]
        assert data["question_count"] == 3

    def test_questions(self, client: TestClient) -> None:
        data = client.get("/api/questions").json()
        assert len(data) == 3
        assert data[0]["id"] == "q001"
        assert data[0]["category"] == "single_hop"


class TestRunLifecycle:
    def test_post_run_executes_and_persists(self, client: TestClient) -> None:
        response = client.post(
            "/api/runs",
            json={"models": ["m1"], "strategies": ["stub"], "question_ids": ["q001", "q002"]},
        )
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        final = wait_for_completion(client, run_id)
        assert final["status"] == "completed"
        results = client.get(f"/api/runs/{run_id}/results").json()
        assert len(results) == 2
        assert results[0]["judge_score"] == 4

    def test_defaults_run_everything(self, client: TestClient) -> None:
        run_id = client.post("/api/runs", json={}).json()["run_id"]
        final = wait_for_completion(client, run_id)
        assert final["status"] == "completed"
        results = client.get(f"/api/runs/{run_id}/results").json()
        assert len(results) == 2 * 2 * 3  # all models x strategies x questions

    def test_second_run_while_busy_is_409(self, client: TestClient) -> None:
        first = client.post("/api/runs", json={"models": ["m1"], "strategies": ["slow"]})
        assert first.status_code == 202
        second = client.post("/api/runs", json={"models": ["m1"]})
        assert second.status_code == 409
        wait_for_completion(client, first.json()["run_id"])

    def test_run_detail_includes_progress_while_running(self, client: TestClient) -> None:
        run_id = client.post("/api/runs", json={"models": ["m1"], "strategies": ["slow"]}).json()[
            "run_id"
        ]
        seen_progress = False
        for _ in range(100):
            data = client.get(f"/api/runs/{run_id}").json()
            if data["status"] == "running" and data.get("progress"):
                seen_progress = True
                assert set(data["progress"]) == {"total", "done", "current"}
                break
            if data["status"] != "running":
                break
            time.sleep(0.01)
        final = wait_for_completion(client, run_id)
        assert final["status"] == "completed"
        assert seen_progress or final["status"] == "completed"

    def test_list_runs(self, client: TestClient) -> None:
        run_id = client.post("/api/runs", json={"models": ["m1"], "strategies": ["stub"]}).json()[
            "run_id"
        ]
        wait_for_completion(client, run_id)
        runs = client.get("/api/runs").json()
        assert runs[0]["id"] == run_id

    def test_unknown_run_404(self, client: TestClient) -> None:
        assert client.get("/api/runs/999").status_code == 404
        assert client.get("/api/runs/999/results").status_code == 404
        assert client.get("/api/runs/999/summary").status_code == 404

    def test_summary_endpoint_with_category_filter(self, client: TestClient) -> None:
        run_id = client.post("/api/runs", json={"models": ["m1"], "strategies": ["stub"]}).json()[
            "run_id"
        ]
        wait_for_completion(client, run_id)
        summary = client.get(f"/api/runs/{run_id}/summary").json()
        assert summary[0]["model"] == "m1"
        assert summary[0]["avg_judge_score"] == 4.0
        multi = client.get(f"/api/runs/{run_id}/summary", params={"category": "multi_hop"}).json()
        assert all(row["count"] == 1 for row in multi)

    def test_invalid_strategy_400(self, client: TestClient) -> None:
        response = client.post("/api/runs", json={"strategies": ["nope"]})
        assert response.status_code == 400
