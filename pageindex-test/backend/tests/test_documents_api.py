"""Documents/jobs API tests with a tmp mount root and in-memory vectors."""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from pageindex_test.config import Settings
from pageindex_test.main import AppDeps, create_app
from pageindex_test.retrieval.vectors import InMemoryVectorIndex


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "root").mkdir()
    return tmp_path / "root"


@pytest.fixture
def client(engine: Engine, root: Path) -> TestClient:
    settings = Settings(_env_file=None, mount_roots_raw=f"{root}=C:\\data")
    index = InMemoryVectorIndex()
    deps = AppDeps(settings=settings, engine=engine, vector_index_factory=lambda location_id: index)
    return TestClient(create_app(deps))


class TestUpload:
    def test_upload_stores_file_and_queues_job(self, client: TestClient, root: Path) -> None:
        response = client.post(
            "/api/documents",
            files={"file": ("notes.md", io.BytesIO(b"# T\n\nbody"), "text/markdown")},
        )
        assert response.status_code == 202
        payload = response.json()
        stored = list(root.glob(".pageindex-test/docs/*/original.md"))
        assert len(stored) == 1
        job = client.get(f"/api/jobs/{payload['job_id']}").json()
        assert job["status"] == "queued"
        assert job["payload"]["doc_id"] == payload["doc_id"]

    def test_unsupported_type_415(self, client: TestClient) -> None:
        response = client.post(
            "/api/documents", files={"file": ("x.xlsx", io.BytesIO(b"z"), "application/xlsx")}
        )
        assert response.status_code == 415


class TestImport:
    def test_import_directory_queues_supported_files(self, client: TestClient, root: Path) -> None:
        (root / "archive").mkdir()
        (root / "archive" / "a.md").write_text("# A", encoding="utf-8")
        (root / "archive" / "b.txt").write_text("text", encoding="utf-8")
        (root / "archive" / "skip.docx").write_text("no", encoding="utf-8")
        response = client.post("/api/documents/import", json={"path": "archive"})
        assert response.status_code == 202
        queued = response.json()["queued"]
        assert {q["filename"] for q in queued} == {"a.md", "b.txt"}

    def test_escape_attempt_400(self, client: TestClient) -> None:
        assert client.post("/api/documents/import", json={"path": "../outside"}).status_code == 400

    def test_missing_path_404(self, client: TestClient) -> None:
        assert client.post("/api/documents/import", json={"path": "nope"}).status_code == 404


class TestListDelete:
    def test_list_and_delete(self, client: TestClient) -> None:
        upload = client.post(
            "/api/documents", files={"file": ("n.md", io.BytesIO(b"# N"), "text/markdown")}
        ).json()
        docs = client.get("/api/documents").json()["documents"]
        assert len(docs) == 1
        assert docs[0]["status"] == "pending"
        assert client.delete(f"/api/documents/{upload['doc_id']}").status_code == 200
        assert client.get("/api/documents").json()["documents"] == []

    def test_get_unknown_404(self, client: TestClient) -> None:
        assert client.get("/api/documents/zzz").status_code == 404
