"""In-process BM25 over the chunks table, rebuilt on ingest completion.

Fine for a prototype corpus (hundreds-to-thousands of docs rebuilds in
milliseconds). Behind a small protocol so a server-mode engine can replace
it without touching the pipeline.
"""

import re
import threading
from dataclasses import dataclass
from typing import Protocol

from rank_bm25 import BM25Okapi

_TOKEN_RE = re.compile(r"\w+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass(frozen=True)
class LexicalHit:
    chunk_id: str
    doc_id: str
    score: float


class LexicalIndex(Protocol):
    def search(self, query: str, limit: int) -> list[LexicalHit]: ...


class Bm25Index:
    """Thread-safe: rebuilt atomically, searched from request threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._bm25: BM25Okapi | None = None
        self._chunk_ids: list[str] = []
        self._doc_ids: list[str] = []

    def rebuild(self, chunk_rows: list[dict]) -> None:
        if not chunk_rows:
            with self._lock:
                self._bm25, self._chunk_ids, self._doc_ids = None, [], []
            return
        corpus = [_tokenize(f"{row['heading_path']} {row['text']}") for row in chunk_rows]
        bm25 = BM25Okapi(corpus)
        with self._lock:
            self._bm25 = bm25
            self._chunk_ids = [row["id"] for row in chunk_rows]
            self._doc_ids = [row["doc_id"] for row in chunk_rows]

    def search(self, query: str, limit: int) -> list[LexicalHit]:
        with self._lock:
            bm25, chunk_ids, doc_ids = self._bm25, self._chunk_ids, self._doc_ids
        if bm25 is None:
            return []
        scores = bm25.get_scores(_tokenize(query))
        ranked = sorted(
            (
                LexicalHit(chunk_id=cid, doc_id=did, score=float(score))
                for cid, did, score in zip(chunk_ids, doc_ids, scores, strict=True)
                if score > 0
            ),
            key=lambda hit: -hit.score,
        )
        return ranked[:limit]
