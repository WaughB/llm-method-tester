"""Logs API filter tests + retention pruning."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from pageindex_test.config import Settings
from pageindex_test.db.schema import logs
from pageindex_test.main import AppDeps, create_app
from pageindex_test.obs.jsonlog import prune_old_logs


def insert_log(engine: Engine, **overrides) -> None:
    row = {
        "ts": datetime.now(UTC).isoformat(),
        "level": "INFO",
        "component": "pipeline",
        "message": "query answered",
        "trace_id": None,
        "data": None,
    }
    row.update(overrides)
    with engine.begin() as conn:
        conn.execute(logs.insert().values(**row))


@pytest.fixture
def client(engine: Engine, tmp_path: Path) -> TestClient:
    (tmp_path / "r").mkdir()
    settings = Settings(_env_file=None, mount_roots_raw=f"{tmp_path / 'r'}=C:\\d")
    deps = AppDeps(
        settings=settings,
        engine=engine,
        query_pipeline=object(),
        lexical_index=object(),
        vector_index_factory=lambda loc: object(),
    )
    return TestClient(create_app(deps))


class TestLogsApi:
    def test_filters_by_level_and_component(self, client: TestClient, engine: Engine) -> None:
        insert_log(engine, level="INFO", component="pipeline")
        insert_log(engine, level="WARNING", component="worker", message="job retried")
        data = client.get("/api/logs", params={"level": "warning"}).json()
        assert data["total"] == 1
        assert data["logs"][0]["message"] == "job retried"
        data = client.get("/api/logs", params={"component": "pipe"}).json()
        assert data["total"] == 1

    def test_filters_by_trace_and_text(self, client: TestClient, engine: Engine) -> None:
        insert_log(engine, trace_id="t-1", message="stage bm25 done")
        insert_log(engine, trace_id="t-2", message="stage answer done")
        data = client.get("/api/logs", params={"trace_id": "t-1"}).json()
        assert data["total"] == 1
        data = client.get("/api/logs", params={"q": "answer"}).json()
        assert data["total"] == 1

    def test_limit_and_newest_first(self, client: TestClient, engine: Engine) -> None:
        for i in range(5):
            insert_log(engine, message=f"m{i}")
        data = client.get("/api/logs", params={"limit": 2}).json()
        assert data["total"] == 5
        assert [r["message"] for r in data["logs"]] == ["m4", "m3"]


class TestRetention:
    def test_prunes_only_old_rows(self, engine: Engine) -> None:
        old = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        insert_log(engine, ts=old, message="ancient")
        insert_log(engine, message="fresh")
        removed = prune_old_logs(engine, retention_days=30)
        assert removed == 1
        with engine.connect() as conn:
            remaining = conn.execute(select(logs.c.message)).fetchall()
        assert [r[0] for r in remaining] == ["fresh"]
