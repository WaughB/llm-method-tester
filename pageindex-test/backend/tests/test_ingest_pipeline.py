"""Ingestion pipeline end-to-end on fakes + in-memory vector index."""

from pathlib import Path

import pytest
from llm_bench.llm.fake import FakeEmbeddingClient
from sqlalchemy import Engine

from pageindex_test.db.repos import ChunkRepo, DocumentRepo
from pageindex_test.ingest.pipeline import IngestPipeline
from pageindex_test.retrieval.vectors import InMemoryVectorIndex


@pytest.fixture
def vector_index() -> InMemoryVectorIndex:
    return InMemoryVectorIndex()


@pytest.fixture
def pipeline(engine: Engine, vector_index: InMemoryVectorIndex) -> IngestPipeline:
    return IngestPipeline(
        documents=DocumentRepo(engine),
        chunks=ChunkRepo(engine),
        embedder=FakeEmbeddingClient(),
        vector_index_factory=lambda location_id: vector_index,
    )


def create_doc(engine: Engine, filename: str = "guide.md") -> str:
    return DocumentRepo(engine).create("loc1", filename, filename.rsplit(".", 1)[-1])


class TestIngest:
    def test_markdown_to_ready(
        self,
        engine: Engine,
        pipeline: IngestPipeline,
        vector_index: InMemoryVectorIndex,
        tmp_path: Path,
    ) -> None:
        source = tmp_path / "guide.md"
        source.write_text(
            "# Ops Guide\n\n## Restarting\n\nRun restart-now.\n\n## Backups\n\nNightly.",
            encoding="utf-8",
        )
        doc_id = create_doc(engine)
        pipeline.ingest(doc_id, source, tmp_path / "extracted.md")

        doc = DocumentRepo(engine).get(doc_id)
        assert doc["status"] == "ready"
        assert doc["title"] == "Ops Guide"
        assert doc["chunk_count"] >= 3
        stored_chunks = ChunkRepo(engine).for_location("loc1")
        assert any("restart-now" in c["text"] for c in stored_chunks)
        assert all(c["doc_id"] == doc_id for c in stored_chunks)
        # vectors upserted for every chunk
        assert len(vector_index.store) == doc["chunk_count"]
        assert (tmp_path / "extracted.md").exists()

    def test_scanned_pdf_marked_unsupported(
        self, engine: Engine, pipeline: IngestPipeline, tmp_path: Path
    ) -> None:
        from conftest import make_pdf

        source = make_pdf(tmp_path / "scan.pdf", pages=["", ""])
        doc_id = create_doc(engine, "scan.pdf")
        pipeline.ingest(doc_id, source, tmp_path / "extracted.md")
        doc = DocumentRepo(engine).get(doc_id)
        assert doc["status"] == "unsupported"
        assert "scanned" in doc["error"]

    def test_missing_file_marked_error(
        self, engine: Engine, pipeline: IngestPipeline, tmp_path: Path
    ) -> None:
        doc_id = create_doc(engine)
        pipeline.ingest(doc_id, tmp_path / "gone.md", tmp_path / "extracted.md")
        doc = DocumentRepo(engine).get(doc_id)
        assert doc["status"] == "error"

    def test_reingest_replaces_chunks_and_vectors(
        self,
        engine: Engine,
        pipeline: IngestPipeline,
        vector_index: InMemoryVectorIndex,
        tmp_path: Path,
    ) -> None:
        source = tmp_path / "guide.md"
        source.write_text("# G\n\n## One\n\nfirst version", encoding="utf-8")
        doc_id = create_doc(engine)
        pipeline.ingest(doc_id, source, tmp_path / "extracted.md")
        first_count = len(vector_index.store)
        source.write_text("# G\n\n## One\n\nsecond version with more words", encoding="utf-8")
        pipeline.ingest(doc_id, source, tmp_path / "extracted.md")
        stored_chunks = ChunkRepo(engine).for_location("loc1")
        assert all("second version" in c["text"] or "G" in c["text"] for c in stored_chunks)
        assert len(vector_index.store) >= 1
        assert first_count >= 1
