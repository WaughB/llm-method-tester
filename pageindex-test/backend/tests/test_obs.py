"""Logging and tracing tests."""

import json
import logging

from sqlalchemy import Engine, select

from pageindex_test.db.schema import logs as logs_table
from pageindex_test.obs.jsonlog import DatabaseLogHandler, JsonFormatter
from pageindex_test.obs.trace import TraceRecorder, bind_trace, current_trace_id


class TestJsonFormatter:
    def test_emits_json_with_fields(self) -> None:
        record = logging.LogRecord("comp.x", logging.INFO, "f", 1, "hello %s", ("world",), None)
        payload = json.loads(JsonFormatter().format(record))
        assert payload["level"] == "INFO"
        assert payload["component"] == "comp.x"
        assert payload["message"] == "hello world"
        assert payload["trace_id"] is None

    def test_includes_bound_trace_id_and_data(self) -> None:
        recorder = TraceRecorder("trace-abc")
        with bind_trace(recorder):
            record = logging.LogRecord("c", logging.INFO, "f", 1, "m", None, None)
            record.data = {"tokens": 5}
            payload = json.loads(JsonFormatter().format(record))
        assert payload["trace_id"] == "trace-abc"
        assert payload["data"] == {"tokens": 5}


class TestDatabaseLogHandler:
    def test_batches_then_flushes_to_db(self, engine: Engine) -> None:
        handler = DatabaseLogHandler(engine, batch_size=3)
        logger = logging.getLogger("db.test")
        logger.setLevel(logging.INFO)
        logger.handlers = [handler]
        logger.propagate = False
        for i in range(2):
            logger.info("msg %d", i)
        with engine.connect() as conn:
            assert len(conn.execute(select(logs_table)).fetchall()) == 0  # buffered
        logger.info("msg 2")  # hits batch_size -> flush
        with engine.connect() as conn:
            rows = conn.execute(select(logs_table)).mappings().fetchall()
        assert [r["message"] for r in rows] == ["msg 0", "msg 1", "msg 2"]

    def test_explicit_flush(self, engine: Engine) -> None:
        handler = DatabaseLogHandler(engine, batch_size=100)
        logger = logging.getLogger("db.test2")
        logger.setLevel(logging.INFO)
        logger.handlers = [handler]
        logger.propagate = False
        logger.warning("pending")
        handler.flush()
        with engine.connect() as conn:
            [row] = conn.execute(select(logs_table)).mappings().fetchall()
        assert row["level"] == "WARNING"


class TestTraceRecorder:
    def test_stages_record_timing_and_metadata(self) -> None:
        recorder = TraceRecorder()
        with recorder.stage("bm25") as stage:
            stage.candidates = 8
        with recorder.stage("answer") as stage:
            stage.tokens = 120
            stage.detail = {"model": "m"}
        stages = recorder.stages_json()
        assert [s["name"] for s in stages] == ["bm25", "answer"]
        assert stages[0]["candidates"] == 8
        assert stages[1]["tokens"] == 120
        assert all(s["ms"] >= 0 for s in stages)

    def test_bind_trace_sets_and_resets_contextvar(self) -> None:
        recorder = TraceRecorder("t-1")
        assert current_trace_id.get() is None
        with bind_trace(recorder):
            assert current_trace_id.get() == "t-1"
        assert current_trace_id.get() is None
