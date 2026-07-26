"""Repository classes over the Core schema. Grows with each phase."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Engine, delete, select

from pageindex_test.db.schema import app_settings, chunks, documents, jobs


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
