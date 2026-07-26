"""Traditional vector RAG: chunk -> embed -> cosine top-k -> context stuffing.

The embedding model is fixed across all chat models under test, so the index
is built once per corpus and only the generation step varies by model.
"""

import time
from typing import ClassVar

from chromadb.api import ClientAPI

from llm_bench.corpus import BenchmarkCorpus
from llm_bench.corpus.qa import Question
from llm_bench.llm.base import EmbeddingClient, GenOptions, LLMClient
from llm_bench.strategies.base import ANSWER_SYSTEM, RetrievalStrategy, StrategyAnswer
from llm_bench.strategies.chunker import Chunk, chunk_document

_PROMPT_TEMPLATE = """Use the following context to answer the question.

Context:
{context}

Question: {question}

Answer concisely using only the context above."""

_EMBED_BATCH_SIZE = 32


class TraditionalRAGStrategy(RetrievalStrategy):
    name: ClassVar[str] = "traditional_rag"
    representation: ClassVar[str | None] = "docs"

    def __init__(
        self,
        llm: LLMClient,
        embedder: EmbeddingClient,
        chroma_client: ClientAPI,
        *,
        top_k: int = 5,
        options: GenOptions | None = None,
    ) -> None:
        self._llm = llm
        self._embedder = embedder
        self._chroma = chroma_client
        self._top_k = top_k
        self._options = options or GenOptions()
        self._collection = None
        self._chunks: dict[str, Chunk] = {}

    def prepare(self, corpus: BenchmarkCorpus, model: str) -> None:
        collection_name = f"docs_{corpus.content_hash()}"
        collection = self._chroma.get_or_create_collection(
            collection_name, metadata={"hnsw:space": "cosine"}
        )
        chunks = [c for doc in corpus.documents for c in chunk_document(doc)]
        self._chunks = {c.chunk_id: c for c in chunks}
        self._collection = collection
        if collection.count() == len(chunks):
            return  # index for this exact corpus already built (persistent client)
        for start in range(0, len(chunks), _EMBED_BATCH_SIZE):
            batch = chunks[start : start + _EMBED_BATCH_SIZE]
            collection.add(
                ids=[c.chunk_id for c in batch],
                embeddings=self._embedder.embed([c.text for c in batch]),
                documents=[c.text for c in batch],
                metadatas=[{"doc_id": c.doc_id} for c in batch],
            )

    def answer(self, question: Question, model: str) -> StrategyAnswer:
        if self._collection is None:
            raise RuntimeError("prepare() must be called before answer()")
        start = time.perf_counter()
        [query_vec] = self._embedder.embed([question.question])
        hits = self._collection.query(
            query_embeddings=[query_vec],
            n_results=min(self._top_k, len(self._chunks)),
            include=["documents", "metadatas"],
        )
        documents = hits["documents"][0]
        doc_ids_ranked = [m["doc_id"] for m in hits["metadatas"][0]]
        retrieved_ids = list(dict.fromkeys(doc_ids_ranked))  # dedup, keep rank order
        context = "\n\n---\n\n".join(documents)
        prompt = _PROMPT_TEMPLATE.format(context=context, question=question.question)
        response = self._llm.generate(model, prompt, system=ANSWER_SYSTEM, options=self._options)
        latency_ms = (time.perf_counter() - start) * 1000
        return StrategyAnswer(
            text=response.text,
            retrieved_ids=retrieved_ids,
            llm_calls=1,
            latency_ms=latency_ms,
            tokens_per_sec=response.tokens_per_sec,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            context_chars=len(context),
        )
