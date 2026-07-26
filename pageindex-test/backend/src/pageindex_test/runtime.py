"""Worker-side composition: registers real job handlers."""

from pathlib import Path

from sqlalchemy import Engine

from pageindex_test.config import Settings
from pageindex_test.worker import JOB_HANDLERS


def register_job_handlers(engine: Engine, settings: Settings) -> None:
    from llm_bench.eval.judge import LLMJudge
    from llm_bench.llm.ollama import OllamaClient, OllamaEmbeddingClient

    from pageindex_test.db.repos import ChunkRepo, DocumentRepo, EvalRepo
    from pageindex_test.evalmode.goldgen import generate_questions
    from pageindex_test.evalmode.runner import EvalRunner
    from pageindex_test.ingest.pipeline import IngestPipeline
    from pageindex_test.main import AppDeps, create_app
    from pageindex_test.retrieval.vectors import QdrantIndex

    documents = DocumentRepo(engine)
    chunk_repo = ChunkRepo(engine)
    eval_repo = EvalRepo(engine)
    llm = OllamaClient(settings.ollama_base_url, timeout_s=settings.request_timeout_s)
    embedder = OllamaEmbeddingClient(settings.ollama_base_url, model=settings.embedding_model)

    pipeline = IngestPipeline(
        documents=documents,
        chunks=chunk_repo,
        embedder=embedder,
        vector_index_factory=lambda location_id: QdrantIndex(settings.qdrant_url, location_id),
    )

    def handle_ingest(job: dict) -> None:
        payload = job["payload"]
        pipeline.ingest(payload["doc_id"], Path(payload["source"]), Path(payload["extracted"]))

    def handle_eval_generate(job: dict) -> None:
        payload = job["payload"]
        location_id = job["location_id"]
        chunks_by_doc: dict[str, list[str]] = {}
        for row in chunk_repo.for_location(location_id):
            chunks_by_doc.setdefault(row["doc_id"], []).append(row["text"])
        for doc_id, texts in chunks_by_doc.items():
            doc = documents.get(doc_id)
            if doc is None or doc["status"] != "ready":
                continue
            for item in generate_questions(
                llm, payload["model"], doc_id, texts, per_doc=payload.get("per_doc", 3)
            ):
                eval_repo.add_question(
                    payload["set_id"],
                    item["question"],
                    item["expected_keywords"],
                    item["gold_doc_ids"],
                    source="generated",
                    approved=False,
                )

    def handle_eval_run(job: dict) -> None:
        # the worker builds the same query pipeline the API uses
        deps = AppDeps(settings=settings, engine=engine)
        create_app(deps)  # populates default components incl. query_pipeline
        deps.lexical_index.rebuild(chunk_repo.for_location(job["location_id"]))
        judge = LLMJudge(client=llm, model=settings.judge_model)
        runner = EvalRunner(eval_repo, deps.query_pipeline, judge)
        run_id = job["payload"]["run_id"]
        try:
            runner.run(run_id)
        except Exception as exc:
            eval_repo.finish_run(run_id, {}, error=str(exc))
            raise

    JOB_HANDLERS["ingest"] = handle_ingest
    JOB_HANDLERS["eval_generate"] = handle_eval_generate
    JOB_HANDLERS["eval_run"] = handle_eval_run
