"""Per-query tracing: a trace_id contextvar and stage timers.

Every log record emitted inside a trace context carries the trace_id, and
each pipeline stage records {name, ms, candidates, tokens, detail} for the
query_traces row — the unit Brett will mine for metrics later.
"""

import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

current_trace_id: ContextVar[str | None] = ContextVar("current_trace_id", default=None)


def new_trace_id() -> str:
    return str(uuid.uuid4())


@dataclass
class StageRecord:
    name: str
    ms: float
    candidates: int = 0
    tokens: int = 0
    detail: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "ms": round(self.ms, 1),
            "candidates": self.candidates,
            "tokens": self.tokens,
            "detail": self.detail,
        }


class TraceRecorder:
    """Collects stage records for one query; bind with the contextvar."""

    def __init__(self, trace_id: str | None = None) -> None:
        self.trace_id = trace_id or new_trace_id()
        self.stages: list[StageRecord] = []
        self._start = time.perf_counter()

    @contextmanager
    def stage(self, name: str):
        record = StageRecord(name=name, ms=0.0)
        start = time.perf_counter()
        try:
            yield record
        finally:
            record.ms = (time.perf_counter() - start) * 1000
            self.stages.append(record)

    @property
    def total_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000

    def stages_json(self) -> list[dict]:
        return [s.as_dict() for s in self.stages]


@contextmanager
def bind_trace(recorder: TraceRecorder):
    token = current_trace_id.set(recorder.trace_id)
    try:
        yield recorder
    finally:
        current_trace_id.reset(token)
