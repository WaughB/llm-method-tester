"""Eval mode: gold generation parsing, runner scoring, API flow."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from llm_bench.eval.judge import LLMJudge
from llm_bench.llm.fake import FakeLLMClient
from sqlalchemy import Engine

from pageindex_test.config import Settings
from pageindex_test.db.repos import EvalRepo
from pageindex_test.evalmode.goldgen import generate_questions
from pageindex_test.evalmode.runner import EvalRunner
from pageindex_test.main import AppDeps, create_app


class TestGoldGen:
    def test_keeps_only_verifiable_keyword_groups(self) -> None:
        llm = FakeLLMClient(
            default=json.dumps(
                {
                    "questions": [
                        {
                            "question": "What port does the control plane use?",
                            "expected_keywords": [["7433"], ["nonexistent-phrase"]],
                        },
                        {"question": "Bad one", "expected_keywords": [["missing-fact"]]},
                    ]
                }
            )
        )
        questions = generate_questions(
            llm, "m", "doc-1", ["The control plane listens on port 7433."]
        )
        assert len(questions) == 1
        assert questions[0]["expected_keywords"] == [["7433"]]
        assert questions[0]["gold_doc_ids"] == ["doc-1"]

    def test_malformed_response_yields_nothing(self) -> None:
        llm = FakeLLMClient(default="I refuse to answer in JSON")
        assert generate_questions(llm, "m", "doc-1", ["text"]) == []


class FakeQueryPipeline:
    """Returns canned answers keyed by question substring."""

    def __init__(self, answers: dict[str, tuple[str, list]]) -> None:
        self.answers = answers
        self.calls: list[dict] = []

    def ask(self, location_id, question, model, *, use_pageindex_stage=True):
        from pageindex_test.pipeline.query import Citation, QueryResult

        self.calls.append({"question": question, "staged": use_pageindex_stage})
        for needle, (answer, doc_ids) in self.answers.items():
            if needle in question:
                return QueryResult(
                    answer=answer,
                    citations=[
                        Citation(doc_id=d, chunk_id=None, heading="H", snippet="s") for d in doc_ids
                    ],
                    trace_id=f"trace-{len(self.calls)}",
                    pipeline="staged" if use_pageindex_stage else "hybrid_only",
                    total_ms=1.0,
                )
        raise AssertionError(f"no canned answer for {question}")


@pytest.fixture
def eval_repo(engine: Engine) -> EvalRepo:
    return EvalRepo(engine)


def make_set_with_questions(repo: EvalRepo) -> str:
    set_id = repo.create_set("loc1", "smoke")
    repo.add_question(set_id, "What port is used?", [["7433"]], ["doc-1"])
    repo.add_question(set_id, "When do backups run?", [["nightly", "02:00"]], ["doc-2"])
    repo.add_question(
        set_id, "Unapproved?", [["zzz"]], ["doc-9"], source="generated", approved=False
    )
    return set_id


class TestEvalRunner:
    def test_scores_approved_questions_and_summarizes(self, eval_repo: EvalRepo) -> None:
        set_id = make_set_with_questions(eval_repo)
        run_id = eval_repo.create_run(set_id, "m", "staged")
        pipeline = FakeQueryPipeline(
            {
                "port": ("The port is 7433.", ["doc-1"]),
                "backups": ("Backups run nightly.", ["doc-3"]),
            }
        )
        judge_llm = FakeLLMClient(
            default=json.dumps({"score": 4, "verdict": "correct", "reasoning": "ok"})
        )
        runner = EvalRunner(eval_repo, pipeline, LLMJudge(client=judge_llm, model="j"))
        runner.run(run_id)

        results = eval_repo.results_for_run(run_id)
        assert len(results) == 2  # unapproved question skipped
        by_answer = {r["answer"]: r for r in results}
        port = by_answer["The port is 7433."]
        assert port["keyword_recall"] == 1.0
        assert port["retrieval_hit"] == 1.0
        assert port["judge_score"] == 4
        backups = by_answer["Backups run nightly."]
        assert backups["retrieval_hit"] == 0.0  # cited doc-3, gold is doc-2

        run = eval_repo.get_run(run_id)
        assert run["status"] == "done"
        assert run["summary"]["count"] == 2
        assert run["summary"]["avg_judge_score"] == 4.0
        # all questions were asked with the staged flag
        assert all(c["staged"] for c in pipeline.calls)

    def test_hybrid_only_run_passes_flag(self, eval_repo: EvalRepo) -> None:
        set_id = make_set_with_questions(eval_repo)
        run_id = eval_repo.create_run(set_id, "m", "hybrid_only")
        pipeline = FakeQueryPipeline(
            {"port": ("7433", ["doc-1"]), "backups": ("nightly", ["doc-2"])}
        )
        EvalRunner(eval_repo, pipeline, judge=None).run(run_id)
        assert all(not c["staged"] for c in pipeline.calls)
        results = eval_repo.results_for_run(run_id)
        assert all(r["judge_score"] is None for r in results)


class TestEvalApi:
    @pytest.fixture
    def client(self, engine: Engine, tmp_path: Path) -> TestClient:
        (tmp_path / "root").mkdir()
        settings = Settings(_env_file=None, mount_roots_raw=f"{tmp_path / 'root'}=C:\\d")
        deps = AppDeps(
            settings=settings,
            engine=engine,
            query_pipeline=object(),
            lexical_index=object(),
            vector_index_factory=lambda loc: object(),
        )
        return TestClient(create_app(deps))

    def test_set_question_run_flow(self, client: TestClient) -> None:
        eval_set = client.post("/api/eval-sets", json={"name": "my set"}).json()
        client.post(
            f"/api/eval-sets/{eval_set['id']}/questions",
            json={
                "question": "Which port?",
                "expected_keywords": [["7433"]],
                "gold_doc_ids": ["doc-1"],
            },
        )
        listing = client.get("/api/eval-sets").json()["sets"]
        assert listing[0]["question_count"] == 1
        assert listing[0]["approved_count"] == 1

        runs = client.post(f"/api/eval-sets/{eval_set['id']}/runs", json={}).json()["runs"]
        assert {r["pipeline"] for r in runs} == {"staged", "hybrid_only"}
        detail = client.get(f"/api/eval-runs/{runs[0]['run_id']}").json()
        assert detail["status"] == "queued"

    def test_generate_queues_job(self, client: TestClient) -> None:
        eval_set = client.post("/api/eval-sets", json={"name": "g"}).json()
        response = client.post(f"/api/eval-sets/{eval_set['id']}/generate", json={})
        assert response.status_code == 202
        job = client.get(f"/api/jobs/{response.json()['job_id']}").json()
        assert job["type"] == "eval_generate"

    def test_approve_toggle(self, client: TestClient) -> None:
        eval_set = client.post("/api/eval-sets", json={"name": "a"}).json()
        question = client.post(
            f"/api/eval-sets/{eval_set['id']}/questions",
            json={"question": "q", "expected_keywords": [["x"]], "gold_doc_ids": ["d"]},
        ).json()
        client.put(f"/api/eval-questions/{question['id']}/approved", json={"approved": False})
        detail = client.get(f"/api/eval-sets/{eval_set['id']}").json()
        assert detail["questions"][0]["approved"] is False

    def test_invalid_pipeline_400(self, client: TestClient) -> None:
        eval_set = client.post("/api/eval-sets", json={"name": "x"}).json()
        response = client.post(
            f"/api/eval-sets/{eval_set['id']}/runs", json={"pipelines": ["quantum"]}
        )
        assert response.status_code == 400
