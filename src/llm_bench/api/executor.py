"""Single-slot background execution of benchmark runs.

The GPU serializes all model work anyway, so exactly one run may be active;
POST /api/runs returns 409 while busy. Progress is shared via a lock for the
polling endpoint.
"""

import contextlib
import threading
from dataclasses import dataclass

from llm_bench.corpus.qa import QADataset
from llm_bench.runner import BenchmarkRunner, RunProgress
from llm_bench.storage.repository import ResultsRepository


class ExecutorBusyError(RuntimeError):
    pass


@dataclass(frozen=True)
class RunRequestSpec:
    models: list[str]
    strategy_names: list[str] | None
    question_ids: list[str] | None


class RunExecutor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._active_run_id: int | None = None
        self._progress: RunProgress | None = None

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(
        self,
        runner: BenchmarkRunner,
        repo: ResultsRepository,
        dataset: QADataset,
        spec: RunRequestSpec,
    ) -> int:
        with self._lock:
            if self.busy:
                raise ExecutorBusyError("a run is already in progress")
            config = {
                "models": spec.models,
                "strategies": spec.strategy_names or runner.available_strategies,
                "question_ids": spec.question_ids or [q.id for q in dataset],
            }
            run_id = repo.create_run(config)
            self._active_run_id = run_id
            self._progress = None
            self._thread = threading.Thread(
                target=self._execute, args=(runner, run_id, spec), daemon=True
            )
            self._thread.start()
            return run_id

    def _execute(self, runner: BenchmarkRunner, run_id: int, spec: RunRequestSpec) -> None:
        # a raising runner has already marked the run as failed in storage
        with contextlib.suppress(Exception):
            runner.run(
                models=spec.models,
                strategy_names=spec.strategy_names,
                question_ids=spec.question_ids,
                resume_run_id=run_id,
                progress=self._on_progress,
            )

    def _on_progress(self, progress: RunProgress) -> None:
        with self._lock:
            self._progress = progress

    def progress_for(self, run_id: int) -> dict | None:
        with self._lock:
            if run_id != self._active_run_id or self._progress is None:
                return None
            return {
                "total": self._progress.total,
                "done": self._progress.done,
                "current": self._progress.current,
            }
