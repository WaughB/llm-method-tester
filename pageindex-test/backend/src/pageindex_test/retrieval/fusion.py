"""Reciprocal rank fusion of lexical and vector rankings.

RRF is rank-based, so BM25 scores and cosine similarities never need to be
calibrated against each other — the standard trick for hybrid retrieval.
"""

from dataclasses import dataclass

_RRF_K = 60


@dataclass(frozen=True)
class FusedHit:
    chunk_id: str
    doc_id: str
    score: float
    in_lexical: bool
    in_vector: bool


def reciprocal_rank_fusion(lexical: list, vector: list, *, limit: int) -> list[FusedHit]:
    """Each input is a ranked list of hits with .chunk_id/.doc_id."""
    scores: dict[str, float] = {}
    doc_by_chunk: dict[str, str] = {}
    seen_lexical: set[str] = set()
    seen_vector: set[str] = set()

    for rank, hit in enumerate(lexical):
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
        doc_by_chunk[hit.chunk_id] = hit.doc_id
        seen_lexical.add(hit.chunk_id)
    for rank, hit in enumerate(vector):
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (_RRF_K + rank + 1)
        doc_by_chunk[hit.chunk_id] = hit.doc_id
        seen_vector.add(hit.chunk_id)

    ranked = sorted(scores.items(), key=lambda item: -item[1])
    return [
        FusedHit(
            chunk_id=chunk_id,
            doc_id=doc_by_chunk[chunk_id],
            score=score,
            in_lexical=chunk_id in seen_lexical,
            in_vector=chunk_id in seen_vector,
        )
        for chunk_id, score in ranked[:limit]
    ]


def top_docs(hits: list[FusedHit], limit: int) -> list[str]:
    """Unique doc ids in fused-rank order."""
    ordered: list[str] = []
    for hit in hits:
        if hit.doc_id not in ordered:
            ordered.append(hit.doc_id)
        if len(ordered) == limit:
            break
    return ordered
