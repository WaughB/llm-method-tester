"""Vector index protocol with Qdrant (runtime) and in-memory (tests) backends.

Collections are per storage location (`chunks_<location_id>`), so switching
the active location swaps vector libraries with zero migration.
"""

import math
import uuid
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class VectorHit:
    chunk_id: str
    doc_id: str
    score: float


class VectorIndex(Protocol):
    def upsert(self, items: list[tuple[str, str, list[float]]]) -> None:
        """items: (chunk_id, doc_id, vector)"""
        ...

    def search(self, vector: list[float], limit: int) -> list[VectorHit]: ...

    def delete_doc(self, doc_id: str) -> None: ...


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class QdrantIndex:
    def __init__(self, url: str, location_id: str) -> None:
        from qdrant_client import QdrantClient

        self._client = QdrantClient(url=url)
        self._collection = f"chunks_{location_id}"
        self._ensured = False

    def _ensure(self, dim: int) -> None:
        from qdrant_client import models

        if self._ensured:
            return
        if not self._client.collection_exists(self._collection):
            self._client.create_collection(
                self._collection,
                vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
            )
        self._ensured = True

    def upsert(self, items: list[tuple[str, str, list[float]]]) -> None:
        from qdrant_client import models

        if not items:
            return
        self._ensure(dim=len(items[0][2]))
        self._client.upsert(
            self._collection,
            points=[
                models.PointStruct(
                    id=_point_id(chunk_id),
                    vector=vector,
                    payload={"chunk_id": chunk_id, "doc_id": doc_id},
                )
                for chunk_id, doc_id, vector in items
            ],
        )

    def search(self, vector: list[float], limit: int) -> list[VectorHit]:
        if not self._client.collection_exists(self._collection):
            return []
        response = self._client.query_points(self._collection, query=vector, limit=limit)
        return [
            VectorHit(
                chunk_id=point.payload["chunk_id"],
                doc_id=point.payload["doc_id"],
                score=point.score,
            )
            for point in response.points
        ]

    def delete_doc(self, doc_id: str) -> None:
        from qdrant_client import models

        if not self._client.collection_exists(self._collection):
            return
        self._client.delete(
            self._collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))
                    ]
                )
            ),
        )


@dataclass
class InMemoryVectorIndex:
    """Deterministic stand-in for tests: exact cosine over a dict."""

    store: dict[str, tuple[str, list[float]]] = field(default_factory=dict)

    def upsert(self, items: list[tuple[str, str, list[float]]]) -> None:
        for chunk_id, doc_id, vector in items:
            self.store[chunk_id] = (doc_id, vector)

    def search(self, vector: list[float], limit: int) -> list[VectorHit]:
        def cosine(a: list[float], b: list[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b, strict=False))
            norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
            return dot / norm if norm else 0.0

        hits = [
            VectorHit(chunk_id=cid, doc_id=doc_id, score=cosine(vector, vec))
            for cid, (doc_id, vec) in self.store.items()
        ]
        return sorted(hits, key=lambda h: -h.score)[:limit]

    def delete_doc(self, doc_id: str) -> None:
        self.store = {cid: (did, vec) for cid, (did, vec) in self.store.items() if did != doc_id}
