"""Benchmark orchestration: the model x strategy x question matrix.

The matrix iterates model-major so Ollama swaps models as rarely as possible
(a model swap on a 10GB-VRAM GPU costs far more than any single question).
Every cell is written to storage immediately and failures land in the row's
`error` column, so a crash or flaky generation never loses a run: rerun with
`resume_run_id` and finished cells are skipped.
"""

from collections.abc import Callable
from dataclasses import dataclass

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import QADataset, Question
from llm_bench.eval.evaluator import Evaluator
from llm_bench.storage.models import ResultRecord
from llm_bench.storage.repository import ResultsRepository
from llm_bench.strategies.base import RetrievalStrategy, StrategyAnswer


@dataclass(frozen=True)
class RunProgress:
    total: int
    done: int
    current: str  # "model / strategy / question_id"


ProgressCallback = Callable[[RunProgress], None]


class BenchmarkRunner:
    def __init__(
        self,
        repo: ResultsRepository,
        corpus: BenchmarkCorpus,
        dataset: QADataset,
        strategies: list[RetrievalStrategy],
        evaluator: Evaluator,
    ) -> None:
        self._repo = repo
        self._corpus = corpus
        self._dataset = dataset
        self._strategies = {s.name: s for s in strategies}
        self._evaluator = evaluator

    @property
    def available_strategies(self) -> list[str]:
        return list(self._strategies)

    def run(
        self,
        models: list[str],
        strategy_names: list[str] | None = None,
        question_ids: list[str] | None = None,
        resume_run_id: int | None = None,
        progress: ProgressCallback | None = None,
    ) -> int:
        strategies = self._select_strategies(strategy_names)
        questions = self._select_questions(question_ids)

        if resume_run_id is not None:
            run_id = resume_run_id
            existing = self._repo.existing_cells(run_id)
        else:
            config = {
                "models": models,
                "strategies": [s.name for s in strategies],
                "question_ids": [q.id for q in questions],
                "corpus_hash": self._corpus.content_hash(),
            }
            run_id = self._repo.create_run(config)
            existing = set()

        total = len(models) * len(strategies) * len(questions)
        done = 0
        try:
            for model in models:
                for strategy in strategies:
                    prepare_error = self._prepare(strategy, model)
                    for question in questions:
                        if (model, strategy.name, question.id) not in existing:
                            self._run_cell(run_id, model, strategy, question, prepare_error)
                        done += 1
                        if progress is not None:
                            progress(
                                RunProgress(
                                    total=total,
                                    done=done,
                                    current=f"{model} / {strategy.name} / {question.id}",
                                )
                            )
            self._judge_pass(run_id, matrix_total=total, progress=progress)
            self._repo.finish_run(run_id, "completed")
        except BaseException as exc:
            self._repo.finish_run(run_id, "failed", error=str(exc))
            raise
        return run_id

    def _judge_pass(
        self, run_id: int, matrix_total: int, progress: ProgressCallback | None
    ) -> None:
        """Judge all unjudged rows after the matrix, so the judge model loads once.

        Judging inline would force Ollama to swap between the model under test
        and the judge model on every single question.
        """
        pending = self._evaluator.judgeable(self._repo.unjudged_results(run_id))
        total = matrix_total + len(pending)
        for i, result in enumerate(pending, start=1):
            cell = f"{result.model} / {result.strategy} / {result.question_id}"
            question = self._dataset.get(result.question_id)
            judge_result = self._evaluator.judge_answer(question, result.answer)
            if judge_result is not None and result.id is not None:
                self._repo.set_judgment(
                    result.id, judge_result.score, judge_result.verdict, judge_result.reasoning
                )
            if progress is not None:
                progress(
                    RunProgress(
                        total=total,
                        done=matrix_total + i,
                        current=f"judging / {cell}",
                    )
                )

    def _select_strategies(self, names: list[str] | None) -> list[RetrievalStrategy]:
        if names is None:
            return list(self._strategies.values())
        missing = [n for n in names if n not in self._strategies]
        if missing:
            raise ValueError(f"Unknown strategies: {missing}")
        return [self._strategies[n] for n in names]

    def _select_questions(self, ids: list[str] | None) -> list[Question]:
        if ids is None:
            return list(self._dataset)
        return [self._dataset.get(i) for i in ids]

    def _prepare(self, strategy: RetrievalStrategy, model: str) -> str | None:
        """Build the strategy's index; a failure poisons all its cells, not the run."""
        try:
            strategy.prepare(self._corpus, model)
            return None
        except Exception as exc:  # noqa: BLE001
            return f"prepare failed: {exc}"

    def _run_cell(
        self,
        run_id: int,
        model: str,
        strategy: RetrievalStrategy,
        question: Question,
        prepare_error: str | None,
    ) -> None:
        if prepare_error is not None:
            self._repo.save_result(
                self._error_record(run_id, model, strategy, question, prepare_error)
            )
            return
        try:
            answer = strategy.answer(question, model)
        except Exception as exc:  # noqa: BLE001 - one bad cell must not kill the run
            self._repo.save_result(self._error_record(run_id, model, strategy, question, str(exc)))
            return
        outcome = self._evaluator.evaluate_metrics(
            question, answer.text, answer.retrieved_ids, strategy.representation
        )
        self._repo.save_result(
            ResultRecord(
                run_id=run_id,
                model=model,
                strategy=strategy.name,
                question_id=question.id,
                category=question.category,
                answer=answer.text,
                retrieved_ids=answer.retrieved_ids,
                latency_ms=answer.latency_ms,
                tokens_per_sec=answer.tokens_per_sec,
                llm_calls=answer.llm_calls,
                prompt_tokens=answer.prompt_tokens,
                completion_tokens=answer.completion_tokens,
                context_chars=answer.context_chars,
                keyword_recall=outcome.keyword_recall,
                retrieval_hit_rate=outcome.retrieval_hit_rate,
                judge_score=None,  # filled by the deferred judge pass
                judge_verdict=None,
                judge_reasoning=None,
                error=None,
            )
        )

    @staticmethod
    def _error_record(
        run_id: int,
        model: str,
        strategy: RetrievalStrategy,
        question: Question,
        error: str,
    ) -> ResultRecord:
        empty = StrategyAnswer(text="")
        return ResultRecord(
            run_id=run_id,
            model=model,
            strategy=strategy.name,
            question_id=question.id,
            category=question.category,
            answer=empty.text,
            retrieved_ids=[],
            latency_ms=0.0,
            tokens_per_sec=0.0,
            llm_calls=0,
            prompt_tokens=0,
            completion_tokens=0,
            context_chars=0,
            keyword_recall=0.0,
            retrieval_hit_rate=None,
            judge_score=None,
            judge_verdict=None,
            judge_reasoning=None,
            error=error,
        )
