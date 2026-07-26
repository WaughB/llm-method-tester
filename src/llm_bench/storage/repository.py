"""SQLite persistence for benchmark runs and per-question results.

A single connection guarded by a lock: the runner writes from a background
thread while API requests read concurrently.
"""

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from llm_bench.storage.models import ResultRecord, RunRecord, SummaryRow

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    config_json TEXT NOT NULL,
    error TEXT
);
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    model TEXT NOT NULL,
    strategy TEXT NOT NULL,
    question_id TEXT NOT NULL,
    category TEXT NOT NULL,
    answer TEXT NOT NULL,
    retrieved_ids_json TEXT NOT NULL,
    latency_ms REAL NOT NULL,
    tokens_per_sec REAL NOT NULL,
    llm_calls INTEGER NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    context_chars INTEGER NOT NULL,
    keyword_recall REAL NOT NULL,
    retrieval_hit_rate REAL,
    judge_score INTEGER,
    judge_verdict TEXT,
    judge_reasoning TEXT,
    error TEXT,
    UNIQUE (run_id, model, strategy, question_id)
);
"""


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


class ResultsRepository:
    def __init__(self, db_path: str | Path) -> None:
        if isinstance(db_path, Path):
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    # -- runs ---------------------------------------------------------------

    def create_run(self, config: dict) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT INTO runs (started_at, status, config_json) VALUES (?, 'running', ?)",
                (_utcnow(), json.dumps(config)),
            )
        return int(cursor.lastrowid)  # type: ignore[arg-type]

    def finish_run(self, run_id: int, status: str, error: str | None = None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE runs SET status = ?, finished_at = ?, error = ? WHERE id = ?",
                (status, _utcnow(), error, run_id),
            )

    def get_run(self, run_id: int) -> RunRecord:
        with self._lock:
            row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"No run with id {run_id}")
        return self._run_from_row(row)

    def list_runs(self) -> list[RunRecord]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM runs ORDER BY id DESC").fetchall()
        return [self._run_from_row(r) for r in rows]

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> RunRecord:
        return RunRecord(
            id=row["id"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            status=row["status"],
            config=json.loads(row["config_json"]),
            error=row["error"],
        )

    # -- results ------------------------------------------------------------

    def save_result(self, result: ResultRecord) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """INSERT INTO results (
                    run_id, model, strategy, question_id, category, answer,
                    retrieved_ids_json, latency_ms, tokens_per_sec, llm_calls,
                    prompt_tokens, completion_tokens, context_chars, keyword_recall,
                    retrieval_hit_rate, judge_score, judge_verdict, judge_reasoning, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.run_id,
                    result.model,
                    result.strategy,
                    result.question_id,
                    result.category,
                    result.answer,
                    json.dumps(result.retrieved_ids),
                    result.latency_ms,
                    result.tokens_per_sec,
                    result.llm_calls,
                    result.prompt_tokens,
                    result.completion_tokens,
                    result.context_chars,
                    result.keyword_recall,
                    result.retrieval_hit_rate,
                    result.judge_score,
                    result.judge_verdict,
                    result.judge_reasoning,
                    result.error,
                ),
            )
        return int(cursor.lastrowid)  # type: ignore[arg-type]

    def unjudged_results(self, run_id: int) -> list[ResultRecord]:
        """Successful rows still awaiting a judge verdict (deferred judge pass)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM results WHERE run_id = ? AND error IS NULL "
                "AND judge_verdict IS NULL ORDER BY id",
                (run_id,),
            ).fetchall()
        return [self._result_from_row(r) for r in rows]

    def set_judgment(self, result_id: int, score: int, verdict: str, reasoning: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE results SET judge_score = ?, judge_verdict = ?, judge_reasoning = ? "
                "WHERE id = ?",
                (score, verdict, reasoning, result_id),
            )

    def results_for_run(self, run_id: int) -> list[ResultRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM results WHERE run_id = ? ORDER BY id", (run_id,)
            ).fetchall()
        return [self._result_from_row(r) for r in rows]

    def existing_cells(self, run_id: int) -> set[tuple[str, str, str]]:
        """(model, strategy, question_id) triples already stored — for resume."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT model, strategy, question_id FROM results WHERE run_id = ?", (run_id,)
            ).fetchall()
        return {(r["model"], r["strategy"], r["question_id"]) for r in rows}

    @staticmethod
    def _result_from_row(row: sqlite3.Row) -> ResultRecord:
        return ResultRecord(
            id=row["id"],
            run_id=row["run_id"],
            model=row["model"],
            strategy=row["strategy"],
            question_id=row["question_id"],
            category=row["category"],
            answer=row["answer"],
            retrieved_ids=json.loads(row["retrieved_ids_json"]),
            latency_ms=row["latency_ms"],
            tokens_per_sec=row["tokens_per_sec"],
            llm_calls=row["llm_calls"],
            prompt_tokens=row["prompt_tokens"],
            completion_tokens=row["completion_tokens"],
            context_chars=row["context_chars"],
            keyword_recall=row["keyword_recall"],
            retrieval_hit_rate=row["retrieval_hit_rate"],
            judge_score=row["judge_score"],
            judge_verdict=row["judge_verdict"],
            judge_reasoning=row["judge_reasoning"],
            error=row["error"],
        )

    # -- aggregates ---------------------------------------------------------

    def summary_for_run(self, run_id: int, category: str | None = None) -> list[SummaryRow]:
        query = """
            SELECT model, strategy,
                   COUNT(*) AS count,
                   SUM(CASE WHEN error IS NOT NULL THEN 1 ELSE 0 END) AS error_count,
                   AVG(judge_score) AS avg_judge_score,
                   AVG(keyword_recall) AS avg_keyword_recall,
                   AVG(retrieval_hit_rate) AS avg_retrieval_hit_rate,
                   AVG(latency_ms) AS avg_latency_ms,
                   AVG(tokens_per_sec) AS avg_tokens_per_sec,
                   AVG(CAST(llm_calls AS REAL)) AS avg_llm_calls
            FROM results WHERE run_id = ?
        """
        params: list = [run_id]
        if category is not None:
            query += " AND category = ?"
            params.append(category)
        query += " GROUP BY model, strategy ORDER BY model, strategy"
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [SummaryRow(**dict(r)) for r in rows]
