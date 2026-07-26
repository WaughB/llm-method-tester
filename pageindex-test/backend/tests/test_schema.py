"""Schema round-trip tests on SQLite (portability proof)."""

from datetime import UTC, datetime

from sqlalchemy import Engine, select

from pageindex_test.db.schema import documents, init_schema, logs, query_traces


def now() -> str:
    return datetime.now(UTC).isoformat()


class TestSchema:
    def test_init_is_idempotent(self, engine: Engine) -> None:
        init_schema(engine)
        init_schema(engine)  # second call must not raise

    def test_document_roundtrip(self, engine: Engine) -> None:
        with engine.begin() as conn:
            conn.execute(
                documents.insert().values(
                    id="doc-1",
                    location_id="loc123",
                    filename="report.pdf",
                    format="pdf",
                    status="pending",
                    created_at=now(),
                )
            )
        with engine.connect() as conn:
            row = conn.execute(select(documents)).mappings().one()
        assert row["status"] == "pending"
        assert row["location_id"] == "loc123"

    def test_trace_json_roundtrip(self, engine: Engine) -> None:
        stages = [{"name": "bm25", "ms": 1.2, "candidates": 8, "tokens": 0, "detail": {}}]
        with engine.begin() as conn:
            conn.execute(
                query_traces.insert().values(
                    trace_id="t-1",
                    location_id="loc123",
                    question="q?",
                    model="m",
                    pipeline="staged",
                    stages=stages,
                    total_ms=12.5,
                    prompt_tokens=100,
                    completion_tokens=20,
                    llm_calls=2,
                    answer="a",
                    sources=[{"doc_id": "doc-1"}],
                    created_at=now(),
                )
            )
        with engine.connect() as conn:
            row = conn.execute(select(query_traces)).mappings().one()
        assert row["stages"] == stages
        assert row["sources"][0]["doc_id"] == "doc-1"

    def test_log_row_with_null_trace(self, engine: Engine) -> None:
        with engine.begin() as conn:
            conn.execute(
                logs.insert().values(
                    ts=now(), level="INFO", component="test", message="hello", data={"k": 1}
                )
            )
        with engine.connect() as conn:
            row = conn.execute(select(logs)).mappings().one()
        assert row["trace_id"] is None
        assert row["data"] == {"k": 1}
