"""Heading-aware chunking for vector RAG.

Documents split at `##` boundaries so chunks align with semantic sections;
oversized sections are windowed with overlap so no fact straddles a hard cut
without appearing whole in at least one chunk.
"""

import re
from dataclasses import dataclass

from llm_bench.corpus.documents import Document

_H2_SPLIT_RE = re.compile(r"^(?=## )", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    chunk_id: str  # "<doc_id>#<n>"
    doc_id: str
    text: str


def chunk_document(doc: Document, *, max_words: int = 400, overlap_words: int = 50) -> list[Chunk]:
    sections = [s for s in _H2_SPLIT_RE.split(doc.text) if s.strip()]
    pieces: list[str] = []
    for section in sections:
        pieces.extend(_window(section, max_words, overlap_words))
    return [
        Chunk(chunk_id=f"{doc.doc_id}#{i}", doc_id=doc.doc_id, text=piece)
        for i, piece in enumerate(pieces)
    ]


def _window(text: str, max_words: int, overlap_words: int) -> list[str]:
    words = text.split()
    if len(words) <= max_words:
        return [text.strip()]
    step = max_words - overlap_words
    windows = []
    for start in range(0, len(words), step):
        window = words[start : start + max_words]
        windows.append(" ".join(window))
        if start + max_words >= len(words):
            break
    return windows
