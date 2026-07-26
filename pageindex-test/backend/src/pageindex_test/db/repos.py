"""Repository classes over the Core schema. Grows with each phase."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Engine, delete, select

from pageindex_test.db.schema import (
    app_settings,
    chunks,
    conversations,
    documents,
    eval_questions,
    eval_results,
    eval_runs,
    eval_sets,
    jobs,
    messages,
    query_traces,
)


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


class SettingsRepo:
    """Key/value app settings (active location, pipeline knobs)."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, key: str, default=None):
        with self._engine.connect() as conn:
            row = conn.execute(
                select(app_settings.c.value).where(app_settings.c.key == key)
            ).fetchone()
        return row[0] if row else default

    def set(self, key: str, value) -> None:
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(app_settings.c.key).where(app_settings.c.key == key)
            ).fetchone()
            if existing:
                conn.execute(
                    app_settings.update().where(app_settings.c.key == key).values(value=value)
                )
            else:
                conn.execute(app_settings.insert().values(key=key, value=value))

    def all(self) -> dict:
        with self._engine.connect() as conn:
            rows = conn.execute(select(app_settings)).fetchall()
        return {row.key: row.value for row in rows}


class DocumentRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create(self, location_id: str, filename: str, format_: str) -> str:
        doc_id = str(uuid.uuid4())
        with self._engine.begin() as conn:
            conn.execute(
                documents.insert().values(
                    id=doc_id,
                    location_id=location_id,
                    filename=filename,
                    format=format_,
                    status="pending",
                    created_at=utcnow(),
                )
            )
        return doc_id

    def update(self, doc_id: str, **values) -> None:
        with self._engine.begin() as conn:
            conn.execute(documents.update().where(documents.c.id == doc_id).values(**values))

    def get(self, doc_id: str) -> dict | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(select(documents).where(documents.c.id == doc_id))
                .mappings()
                .fetchone()
            )
        return dict(row) if row else None

    def list_for_location(self, location_id: str) -> list[dict]:
        with self._engine.connect() as conn:
            rows = (
                conn.execute(
                    select(documents)
                    .where(documents.c.location_id == location_id)
                    .order_by(documents.c.created_at.desc())
                )
                .mappings()
                .fetchall()
            )
        return [dict(r) for r in rows]

    def delete(self, doc_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(delete(chunks).where(chunks.c.doc_id == doc_id))
            conn.execute(delete(documents).where(documents.c.id == doc_id))


class ChunkRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def replace_for_doc(self, doc_id: str, location_id: str, chunk_rows: list[dict]) -> None:
        with self._engine.begin() as conn:
            conn.execute(delete(chunks).where(chunks.c.doc_id == doc_id))
            if chunk_rows:
                conn.execute(chunks.insert(), chunk_rows)

    def for_location(self, location_id: str) -> list[dict]:
        with self._engine.connect() as conn:
            rows = (
                conn.execute(select(chunks).where(chunks.c.location_id == location_id))
                .mappings()
                .fetchall()
            )
        return [dict(r) for r in rows]

    def get_many(self, chunk_ids: list[str]) -> list[dict]:
        if not chunk_ids:
            return []
        with self._engine.connect() as conn:
            rows = (
                conn.execute(select(chunks).where(chunks.c.id.in_(chunk_ids))).mappings().fetchall()
            )
        by_id = {r["id"]: dict(r) for r in rows}
        return [by_id[cid] for cid in chunk_ids if cid in by_id]


class JobRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def enqueue(self, location_id: str, job_type: str, payload: dict) -> int:
        with self._engine.begin() as conn:
            result = conn.execute(
                jobs.insert().values(
                    location_id=location_id,
                    type=job_type,
                    payload=payload,
                    status="queued",
                    attempts=0,
                    created_at=utcnow(),
                )
            )
        return int(result.inserted_primary_key[0])

    def get(self, job_id: int) -> dict | None:
        with self._engine.connect() as conn:
            row = conn.execute(select(jobs).where(jobs.c.id == job_id)).mappings().fetchone()
        return dict(row) if row else None

    def list_recent(self, status: str | None = None, limit: int = 50) -> list[dict]:
        query = select(jobs).order_by(jobs.c.id.desc()).limit(limit)
        if status:
            query = query.where(jobs.c.status == status)
        with self._engine.connect() as conn:
            rows = conn.execute(query).mappings().fetchall()
        return [dict(r) for r in rows]


class ConversationRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create(self, location_id: str, title: str, model: str) -> str:
        conversation_id = str(uuid.uuid4())
        with self._engine.begin() as conn:
            conn.execute(
                conversations.insert().values(
                    id=conversation_id,
                    location_id=location_id,
                    title=title,
                    model=model,
                    use_pageindex_stage=True,
                    created_at=utcnow(),
                )
            )
        return conversation_id

    def get(self, conversation_id: str) -> dict | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(select(conversations).where(conversations.c.id == conversation_id))
                .mappings()
                .fetchone()
            )
        return dict(row) if row else None

    def list_for_location(self, location_id: str) -> list[dict]:
        with self._engine.connect() as conn:
            rows = (
                conn.execute(
                    select(conversations)
                    .where(conversations.c.location_id == location_id)
                    .order_by(conversations.c.created_at.desc())
                )
                .mappings()
                .fetchall()
            )
        return [dict(r) for r in rows]

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        citations: list | None = None,
        trace_id: str | None = None,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                messages.insert().values(
                    conversation_id=conversation_id,
                    role=role,
                    content=content,
                    citations=citations,
                    trace_id=trace_id,
                    created_at=utcnow(),
                )
            )

    def messages_for(self, conversation_id: str) -> list[dict]:
        with self._engine.connect() as conn:
            rows = (
                conn.execute(
                    select(messages)
                    .where(messages.c.conversation_id == conversation_id)
                    .order_by(messages.c.id)
                )
                .mappings()
                .fetchall()
            )
        return [dict(r) for r in rows]


class EvalRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # sets ------------------------------------------------------------------

    def create_set(self, location_id: str, name: str) -> str:
        set_id = str(uuid.uuid4())
        with self._engine.begin() as conn:
            conn.execute(
                eval_sets.insert().values(
                    id=set_id, location_id=location_id, name=name, created_at=utcnow()
                )
            )
        return set_id

    def get_set(self, set_id: str) -> dict | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(select(eval_sets).where(eval_sets.c.id == set_id))
                .mappings()
                .fetchone()
            )
        return dict(row) if row else None

    def list_sets(self, location_id: str) -> list[dict]:
        with self._engine.connect() as conn:
            rows = (
                conn.execute(
                    select(eval_sets)
                    .where(eval_sets.c.location_id == location_id)
                    .order_by(eval_sets.c.created_at.desc())
                )
                .mappings()
                .fetchall()
            )
        return [dict(r) for r in rows]

    # questions -------------------------------------------------------------

    def add_question(
        self,
        set_id: str,
        question: str,
        expected_keywords: list[list[str]],
        gold_doc_ids: list[str],
        *,
        source: str = "manual",
        approved: bool = True,
    ) -> str:
        question_id = str(uuid.uuid4())
        with self._engine.begin() as conn:
            conn.execute(
                eval_questions.insert().values(
                    id=question_id,
                    set_id=set_id,
                    question=question,
                    expected_keywords=expected_keywords,
                    gold_doc_ids=gold_doc_ids,
                    source=source,
                    approved=approved,
                )
            )
        return question_id

    def questions_for(self, set_id: str) -> list[dict]:
        with self._engine.connect() as conn:
            rows = (
                conn.execute(select(eval_questions).where(eval_questions.c.set_id == set_id))
                .mappings()
                .fetchall()
            )
        return [dict(r) for r in rows]

    def set_approved(self, question_id: str, approved: bool) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                eval_questions.update()
                .where(eval_questions.c.id == question_id)
                .values(approved=approved)
            )

    def delete_question(self, question_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(delete(eval_questions).where(eval_questions.c.id == question_id))

    # runs ------------------------------------------------------------------

    def create_run(self, set_id: str, model: str, pipeline: str) -> str:
        run_id = str(uuid.uuid4())
        with self._engine.begin() as conn:
            conn.execute(
                eval_runs.insert().values(
                    id=run_id, set_id=set_id, model=model, pipeline=pipeline, status="queued"
                )
            )
        return run_id

    def get_run(self, run_id: str) -> dict | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(select(eval_runs).where(eval_runs.c.id == run_id))
                .mappings()
                .fetchone()
            )
        return dict(row) if row else None

    def runs_for_set(self, set_id: str) -> list[dict]:
        with self._engine.connect() as conn:
            rows = (
                conn.execute(select(eval_runs).where(eval_runs.c.set_id == set_id))
                .mappings()
                .fetchall()
            )
        return [dict(r) for r in rows]

    def start_run(self, run_id: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                eval_runs.update()
                .where(eval_runs.c.id == run_id)
                .values(status="running", started_at=utcnow())
            )

    def finish_run(self, run_id: str, summary: dict, *, error: str | None = None) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                eval_runs.update()
                .where(eval_runs.c.id == run_id)
                .values(
                    status="error" if error else "done",
                    finished_at=utcnow(),
                    summary=dict(summary, error=error) if error else summary,
                )
            )

    def save_result(self, run_id: str, **values) -> None:
        with self._engine.begin() as conn:
            conn.execute(eval_results.insert().values(run_id=run_id, **values))

    def results_for_run(self, run_id: str) -> list[dict]:
        with self._engine.connect() as conn:
            rows = (
                conn.execute(select(eval_results).where(eval_results.c.run_id == run_id))
                .mappings()
                .fetchall()
            )
        return [dict(r) for r in rows]

    def summarize_run(self, run_id: str) -> dict:
        results = self.results_for_run(run_id)
        if not results:
            return {"count": 0}

        def avg(key: str) -> float | None:
            values = [r[key] for r in results if r[key] is not None]
            return round(sum(values) / len(values), 3) if values else None

        return {
            "count": len(results),
            "avg_keyword_recall": avg("keyword_recall"),
            "avg_retrieval_hit": avg("retrieval_hit"),
            "avg_judge_score": avg("judge_score"),
        }


class TraceRepo:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, trace_id: str) -> dict | None:
        with self._engine.connect() as conn:
            row = (
                conn.execute(select(query_traces).where(query_traces.c.trace_id == trace_id))
                .mappings()
                .fetchone()
            )
        return dict(row) if row else None
