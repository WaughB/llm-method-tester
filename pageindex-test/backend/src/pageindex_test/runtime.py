"""Worker-side composition: registers real job handlers."""

from pathlib import Path

from sqlalchemy import Engine

from pageindex_test.config import Settings
from pageindex_test.worker import JOB_HANDLERS


def register_job_handlers(engine: Engine, settings: Settings) -> None:
    from llm_bench.llm.ollama import OllamaEmbeddingClient

    from pageindex_test.db.repos import ChunkRepo, DocumentRepo
    from pageindex_test.ingest.pipeline import IngestPipeline
    from pageindex_test.retrieval.vectors import QdrantIndex

    pipeline = IngestPipeline(
        documents=DocumentRepo(engine),
        chunks=ChunkRepo(engine),
        embedder=OllamaEmbeddingClient(settings.ollama_base_url, model=settings.embedding_model),
        vector_index_factory=lambda location_id: QdrantIndex(settings.qdrant_url, location_id),
    )

    def handle_ingest(job: dict) -> None:
        payload = job["payload"]
        pipeline.ingest(payload["doc_id"], Path(payload["source"]), Path(payload["extracted"]))

    JOB_HANDLERS["ingest"] = handle_ingest
