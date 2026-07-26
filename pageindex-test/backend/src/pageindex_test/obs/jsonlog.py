"""JSON logging to stdout (docker logs) and, batched, to the logs table.

The database handler buffers records and flushes on size or age so the hot
path never blocks on Postgres; flush failures fall back to stderr rather
than recursing into logging.
"""

import json
import logging
import sys
import threading
import time
from datetime import UTC, datetime

from sqlalchemy import Engine

from pageindex_test.db.schema import logs as logs_table
from pageindex_test.obs.trace import current_trace_id


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": _utcnow(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
            "trace_id": current_trace_id.get(),
        }
        data = getattr(record, "data", None)
        if data:
            payload["data"] = data
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class DatabaseLogHandler(logging.Handler):
    def __init__(
        self, engine: Engine, *, batch_size: int = 20, flush_interval_s: float = 2.0
    ) -> None:
        super().__init__()
        self._engine = engine
        self._batch_size = batch_size
        self._flush_interval_s = flush_interval_s
        self._buffer: list[dict] = []
        self._lock = threading.Lock()
        self._last_flush = time.monotonic()

    def emit(self, record: logging.LogRecord) -> None:
        data = getattr(record, "data", None)
        exc = None
        if record.exc_info and record.exc_info[0] is not None:
            exc = logging.Formatter().formatException(record.exc_info)
            data = dict(data or {}, exception=exc)
        row = {
            "ts": _utcnow(),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
            "trace_id": current_trace_id.get(),
            "data": data,
        }
        with self._lock:
            self._buffer.append(row)
            due = (
                len(self._buffer) >= self._batch_size
                or time.monotonic() - self._last_flush > self._flush_interval_s
            )
            if due:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buffer:
            return
        rows, self._buffer = self._buffer, []
        self._last_flush = time.monotonic()
        try:
            with self._engine.begin() as conn:
                conn.execute(logs_table.insert(), rows)
        except Exception as exc:  # pragma: no cover - defensive fallback
            print(f"[jsonlog] failed to persist {len(rows)} log rows: {exc}", file=sys.stderr)

    def close(self) -> None:
        self.flush()
        super().close()


def configure_logging(engine: Engine | None = None, level: int = logging.INFO) -> None:
    """Root config: JSON to stdout always; DB handler when an engine is given."""
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(JsonFormatter())
    root.addHandler(stdout_handler)
    if engine is not None:
        root.addHandler(DatabaseLogHandler(engine))
    # keep uvicorn's access noise out of the metrics-bearing log table
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
