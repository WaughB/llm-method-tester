"""Ingestion: extract -> chunk -> embed -> index, run by the worker.

Reuses the benchmark's heading-aware chunker. Failure taxonomy matters here:
UnsupportedDocumentError -> status 'unsupported' with a human-readable reason
(the honest outcome for scanned PDFs); anything else -> status 'error'.
"""

import logging
from pathlib import Path

from llm_bench.corpus.documents import Document
from llm_bench.llm.base import EmbeddingClient
from llm_bench.strategies.chunker import chunk_document

from pageindex_test.db.repos import ChunkRepo, DocumentRepo
from pageindex_test.ingest.extract import UnsupportedDocumentError, extract

logger = logging.getLogger("pageindex_test.ingest")

_EMBED_BATCH = 32


class IngestPipeline:
    def __init__(
        self,
        documents: DocumentRepo,
        chunks: ChunkRepo,
        embedder: EmbeddingClient,
        vector_index_factory,  # Callable[[location_id], VectorIndex]
    ) -> None:
        self._documents = documents
        self._chunks = chunks
        self._embedder = embedder
        self._vector_index_factory = vector_index_factory

    def ingest(self, doc_id: str, source_path: Path, extracted_path: Path) -> None:
        doc = self._documents.get(doc_id)
        if doc is None:
            raise KeyError(f"Unknown document {doc_id}")
        location_id = doc["location_id"]
        self._documents.update(doc_id, status="processing")
        try:
            extracted = extract(source_path)
        except UnsupportedDocumentError as exc:
            logger.warning(
                "document unsupported",
                extra={"data": {"doc_id": doc_id, "reason": str(exc)}},
            )
            self._documents.update(doc_id, status="unsupported", error=str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - error status, not a crashed worker
            logger.exception("extraction failed", extra={"data": {"doc_id": doc_id}})
            self._documents.update(doc_id, status="error", error=str(exc))
            return

        extracted_path.parent.mkdir(parents=True, exist_ok=True)
        extracted_path.write_text(extracted.markdown, encoding="utf-8", newline="\n")

        pieces = chunk_document(
            Document(doc_id=doc_id, title=extracted.title, text=extracted.markdown)
        )
        chunk_rows = [
            {
                "id": piece.chunk_id,
                "doc_id": doc_id,
                "location_id": location_id,
                "ordinal": i,
                "heading_path": _first_heading(piece.text),
                "text": piece.text,
                "token_estimate": max(1, len(piece.text) // 4),
            }
            for i, piece in enumerate(pieces)
        ]
        self._chunks.replace_for_doc(doc_id, location_id, chunk_rows)

        index = self._vector_index_factory(location_id)
        index.delete_doc(doc_id)
        for start in range(0, len(chunk_rows), _EMBED_BATCH):
            batch = chunk_rows[start : start + _EMBED_BATCH]
            vectors = self._embedder.embed([row["text"] for row in batch])
            index.upsert(
                [(row["id"], doc_id, vec) for row, vec in zip(batch, vectors, strict=True)]
            )

        self._documents.update(
            doc_id,
            status="ready",
            title=extracted.title,
            pages=extracted.pages,
            chunk_count=len(chunk_rows),
            error=None,
        )
        logger.info(
            "document ready",
            extra={"data": {"doc_id": doc_id, "chunks": len(chunk_rows)}},
        )


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return ""
