"""Worker claim/finish semantics on the jobs table."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, select

from pageindex_test.db.schema import jobs
from pageindex_test.worker import JOB_HANDLERS, claim_next_job, finish_job, process_one


def enqueue(engine: Engine, job_type: str = "ingest", payload: dict | None = None) -> int:
    with engine.begin() as conn:
        result = conn.execute(
            jobs.insert().values(
                location_id="loc1",
                type=job_type,
                payload=payload or {},
                status="queued",
                attempts=0,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
    return int(result.inserted_primary_key[0])


@pytest.fixture(autouse=True)
def clean_handlers():
    saved = dict(JOB_HANDLERS)
    JOB_HANDLERS.clear()
    yield
    JOB_HANDLERS.clear()
    JOB_HANDLERS.update(saved)


class TestClaiming:
    def test_claims_oldest_and_marks_running(self, engine: Engine) -> None:
        first = enqueue(engine)
        enqueue(engine)
        job = claim_next_job(engine)
        assert job is not None
        assert job["id"] == first
        assert job["status"] == "running"
        assert job["attempts"] == 1

    def test_empty_queue_returns_none(self, engine: Engine) -> None:
        assert claim_next_job(engine) is None

    def test_finish_success_and_error(self, engine: Engine) -> None:
        job_id = enqueue(engine)
        claim_next_job(engine)
        finish_job(engine, job_id)
        with engine.connect() as conn:
            row = conn.execute(select(jobs).where(jobs.c.id == job_id)).mappings().one()
        assert row["status"] == "done"
        assert row["finished_at"]

        job2 = enqueue(engine)
        claim_next_job(engine)
        finish_job(engine, job2, error="boom")
        with engine.connect() as conn:
            row = conn.execute(select(jobs).where(jobs.c.id == job2)).mappings().one()
        assert row["status"] == "error"
        assert row["error"] == "boom"


class TestProcessOne:
    def test_runs_registered_handler(self, engine: Engine) -> None:
        seen: list[dict] = []
        JOB_HANDLERS["ingest"] = seen.append
        enqueue(engine, payload={"doc_id": "d1"})
        assert process_one(engine) is True
        assert seen[0]["payload"] == {"doc_id": "d1"}
        with engine.connect() as conn:
            row = conn.execute(select(jobs)).mappings().one()
        assert row["status"] == "done"

    def test_handler_exception_marks_error_not_crash(self, engine: Engine) -> None:
        def exploding(job: dict) -> None:
            raise RuntimeError("kaput")

        JOB_HANDLERS["ingest"] = exploding
        enqueue(engine)
        assert process_one(engine) is True
        with engine.connect() as conn:
            row = conn.execute(select(jobs)).mappings().one()
        assert row["status"] == "error"
        assert "kaput" in row["error"]

    def test_unknown_type_marked_error(self, engine: Engine) -> None:
        enqueue(engine, job_type="mystery")
        assert process_one(engine) is True
        with engine.connect() as conn:
            row = conn.execute(select(jobs)).mappings().one()
        assert "no handler" in row["error"]

    def test_empty_queue_returns_false(self, engine: Engine) -> None:
        assert process_one(engine) is False
