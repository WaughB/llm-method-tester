"""Chat flow end-to-end on fakes: hybrid retrieval -> answer -> trace row."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from llm_bench.llm.fake import FakeEmbeddingClient, FakeLLMClient
from sqlalchemy import Engine

from pageindex_test.config import Settings
from pageindex_test.db.repos import ChunkRepo, DocumentRepo
from pageindex_test.main import AppDeps, create_app
from pageindex_test.pipeline.query import QueryPipeline
from pageindex_test.retrieval.lexical import Bm25Index
from pageindex_test.retrieval.vectors import InMemoryVectorIndex


@pytest.fixture
def app_client(engine: Engine, tmp_path: Path) -> TestClient:
    (tmp_path / "root").mkdir()
    settings = Settings(_env_file=None, mount_roots_raw=f"{tmp_path / 'root'}=C:\\data")
    embedder = FakeEmbeddingClient()
    vector_index = InMemoryVectorIndex()
    lexical = Bm25Index()
    llm = FakeLLMClient(default="The port is 7433, per the configuration guide.")
    pipeline = QueryPipeline(
        engine=engine,
        chunks=ChunkRepo(engine),
        lexical=lexical,
        embedder=embedder,
        vector_index_factory=lambda location_id: vector_index,
        llm=llm,
        hybrid_top_n=4,
    )
    deps = AppDeps(
        settings=settings,
        engine=engine,
        vector_index_factory=lambda location_id: vector_index,
        lexical_index=lexical,
        query_pipeline=pipeline,
    )
    client = TestClient(create_app(deps))
    client.fake_llm = llm  # type: ignore[attr-defined]
    client.embedder = embedder  # type: ignore[attr-defined]
    client.vector_index = vector_index  # type: ignore[attr-defined]
    return client


def seed_chunks(client: TestClient, engine: Engine) -> str:
    location_id = client.get("/api/locations").json()["locations"][0]["location_id"]
    doc_id = DocumentRepo(engine).create(location_id, "config.md", "md")
    rows = [
        {
            "id": f"{doc_id}#0",
            "doc_id": doc_id,
            "location_id": location_id,
            "ordinal": 0,
            "heading_path": "Network ports",
            "text": "The control plane listens on port 7433.",
            "token_estimate": 12,
        },
        {
            "id": f"{doc_id}#1",
            "doc_id": doc_id,
            "location_id": location_id,
            "ordinal": 1,
            "heading_path": "Backups",
            "text": "Backups run nightly at 02:00.",
            "token_estimate": 10,
        },
    ]
    ChunkRepo(engine).replace_for_doc(doc_id, location_id, rows)
    vectors = client.embedder.embed([r["text"] for r in rows])
    client.vector_index.upsert([(r["id"], doc_id, v) for r, v in zip(rows, vectors, strict=True)])
    return doc_id


class TestChatFlow:
    def test_conversation_lifecycle_with_cited_answer_and_trace(
        self, app_client: TestClient, engine: Engine
    ) -> None:
        doc_id = seed_chunks(app_client, engine)
        conversation = app_client.post("/api/conversations", json={"title": "ports"}).json()
        assert conversation["model"] == "llama3.1:8b"

        response = app_client.post(
            f"/api/conversations/{conversation['id']}/messages",
            json={"question": "Which port does the control plane use?"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert "7433" in payload["answer"]
        assert payload["pipeline"] == "hybrid_only"  # no tree stage wired in P4
        assert any(c["doc_id"] == doc_id for c in payload["citations"])
        assert any(c["heading"] == "Network ports" for c in payload["citations"])

        stage_names = [s["name"] for s in payload["stages"]]
        assert stage_names == ["bm25", "vector", "fusion", "answer"]

        trace = app_client.get(f"/api/traces/{payload['trace_id']}").json()
        assert trace["question"] == "Which port does the control plane use?"
        assert trace["llm_calls"] == 1
        assert trace["prompt_tokens"] > 0
        assert trace["answer"] == payload["answer"]

        # history persisted
        full = app_client.get(f"/api/conversations/{conversation['id']}").json()
        roles = [m["role"] for m in full["messages"]]
        assert roles == ["user", "assistant"]
        assert full["messages"][1]["trace_id"] == payload["trace_id"]

    def test_context_reaches_the_model(self, app_client: TestClient, engine: Engine) -> None:
        seed_chunks(app_client, engine)
        conversation = app_client.post("/api/conversations", json={}).json()
        app_client.post(
            f"/api/conversations/{conversation['id']}/messages",
            json={"question": "When do backups run?"},
        )
        prompt = app_client.fake_llm.calls[-1].prompt
        assert "Backups run nightly" in prompt
        assert "When do backups run?" in prompt

    def test_staged_pipeline_runs_tree_stages(self, engine: Engine, tmp_path: Path) -> None:
        import json as jsonlib

        from pageindex_test.retrieval.trees import TreeStage

        root = tmp_path / "root"
        root.mkdir()
        settings = Settings(_env_file=None, mount_roots_raw=f"{root}=C:\\data")
        embedder = FakeEmbeddingClient()
        vector_index = InMemoryVectorIndex()
        lexical = Bm25Index()
        llm = FakeLLMClient(
            responses={
                "navigating tables of contents": jsonlib.dumps({"node_ids": ["n0002"]}),
            },
            default="Restart with restart-now.",
        )
        library = root / ".pageindex-test"
        tree_stage = TreeStage(
            llm=llm,
            tree_cache_dir_resolver=lambda loc: library / "trees",
            extracted_path_resolver=lambda loc, doc_id: library / "docs" / doc_id / "extracted.md",
            doc_title_resolver=lambda doc_id: "Ops",
        )
        pipeline = QueryPipeline(
            engine=engine,
            chunks=ChunkRepo(engine),
            lexical=lexical,
            embedder=embedder,
            vector_index_factory=lambda location_id: vector_index,
            llm=llm,
            hybrid_top_n=4,
            tree_stage=tree_stage,
        )
        deps = AppDeps(
            settings=settings,
            engine=engine,
            vector_index_factory=lambda location_id: vector_index,
            lexical_index=lexical,
            query_pipeline=pipeline,
        )
        client = TestClient(create_app(deps))
        client.fake_llm = llm  # type: ignore[attr-defined]
        client.embedder = embedder  # type: ignore[attr-defined]
        client.vector_index = vector_index  # type: ignore[attr-defined]
        doc_id = seed_chunks(client, engine)
        doc_dir = library / "docs" / doc_id
        doc_dir.mkdir(parents=True)
        (doc_dir / "extracted.md").write_text(
            "# Ops\n\n## Restarting\n\nUse restart-now.\n\n## Other\n\nnothing",
            encoding="utf-8",
        )

        conversation = client.post("/api/conversations", json={}).json()
        payload = client.post(
            f"/api/conversations/{conversation['id']}/messages",
            json={"question": "How do I restart?", "use_pageindex_stage": True},
        ).json()
        assert payload["pipeline"] == "staged"
        stage_names = [s["name"] for s in payload["stages"]]
        assert stage_names == ["bm25", "vector", "fusion", "tree_build", "tree_select", "answer"]
        assert payload["citations"][0]["heading"] == "Restarting"
        trace = client.get(f"/api/traces/{payload['trace_id']}").json()
        assert trace["pipeline"] == "staged"
        assert trace["llm_calls"] == 2  # tree select + answer

    def test_staged_falls_back_visibly_when_no_trees(
        self, app_client: TestClient, engine: Engine
    ) -> None:
        # app_client's pipeline has no tree_stage -> pipeline reports hybrid_only;
        # here we exercise the explicit fallback path with a stage that raises
        from pageindex_test.retrieval.trees import TreeStageOverBudget

        class ExplodingTreeStage:
            def run(self, *args, **kwargs):
                raise TreeStageOverBudget("no trees for these docs")

        seed_chunks(app_client, engine)
        deps = app_client.app.state.deps  # type: ignore[attr-defined]
        deps.query_pipeline._tree_stage = ExplodingTreeStage()
        conversation = app_client.post("/api/conversations", json={}).json()
        payload = app_client.post(
            f"/api/conversations/{conversation['id']}/messages",
            json={"question": "Which port?", "use_pageindex_stage": True},
        ).json()
        assert payload["pipeline"] == "hybrid_only"
        stage_names = [s["name"] for s in payload["stages"]]
        assert "tree_fallback" in stage_names
        assert "7433" in payload["answer"]

    def test_unknown_conversation_404(self, app_client: TestClient) -> None:
        response = app_client.post("/api/conversations/zzz/messages", json={"question": "q"})
        assert response.status_code == 404

    def test_unknown_trace_404(self, app_client: TestClient) -> None:
        assert app_client.get("/api/traces/none").status_code == 404
