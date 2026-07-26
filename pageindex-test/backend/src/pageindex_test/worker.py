"""Job worker: polls the jobs table, claims with SKIP LOCKED, executes.

Phase 1 ships the loop and claim semantics; job executors register in later
phases via the JOB_HANDLERS mapping.
"""

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import Engine, text

from pageindex_test.db.schema import jobs

logger = logging.getLogger("pageindex_test.worker")

JobHandler = Callable[[dict], None]
JOB_HANDLERS: dict[str, JobHandler] = {}


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def claim_next_job(engine: Engine) -> dict | None:
    """Atomically claim the oldest queued job. Postgres uses SKIP LOCKED;
    SQLite (tests) falls back to a plain transaction, which is fine
    single-worker."""
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "postgresql":
            row = conn.execute(
                text(
                    "SELECT id FROM jobs WHERE status = 'queued' "
                    "ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED"
                )
            ).fetchone()
        else:
            row = conn.execute(
                text("SELECT id FROM jobs WHERE status = 'queued' ORDER BY id LIMIT 1")
            ).fetchone()
        if row is None:
            return None
        conn.execute(
            jobs.update()
            .where(jobs.c.id == row[0])
            .values(status="running", started_at=_utcnow(), attempts=jobs.c.attempts + 1)
        )
        claimed = conn.execute(jobs.select().where(jobs.c.id == row[0])).mappings().fetchone()
        return dict(claimed) if claimed else None


def finish_job(engine: Engine, job_id: int, *, error: str | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(
            jobs.update()
            .where(jobs.c.id == job_id)
            .values(
                status="error" if error else "done",
                error=error,
                finished_at=_utcnow(),
            )
        )


def process_one(engine: Engine) -> bool:
    """Claim and run one job; returns False when the queue is empty."""
    job = claim_next_job(engine)
    if job is None:
        return False
    handler = JOB_HANDLERS.get(job["type"])
    logger.info("job started", extra={"data": {"job_id": job["id"], "type": job["type"]}})
    if handler is None:
        finish_job(engine, job["id"], error=f"no handler for job type {job['type']!r}")
        return True
    try:
        handler(job)
    except Exception as exc:  # noqa: BLE001 - a job failure must not kill the worker
        logger.exception("job failed", extra={"data": {"job_id": job["id"]}})
        finish_job(engine, job["id"], error=str(exc))
        return True
    finish_job(engine, job["id"])
    logger.info("job done", extra={"data": {"job_id": job["id"]}})
    return True


def run_forever(engine: Engine, poll_interval_s: float = 1.0) -> None:  # pragma: no cover
    logger.info("worker started")
    while True:
        worked = process_one(engine)
        if not worked:
            time.sleep(poll_interval_s)
