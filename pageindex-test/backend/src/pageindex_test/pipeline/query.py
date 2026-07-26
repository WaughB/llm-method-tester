"""Query orchestration with full per-stage tracing.

Stage 1: BM25 + vector search fused with RRF.
Stage 2 (optional, Phase 5): PageIndex tree precision over the top docs.
Stage 3: answer generation with citations.

Every query writes a query_traces row — the unit of later metrics mining.
"""

import logging
from dataclasses import dataclass, field

from llm_bench.llm.base import EmbeddingClient, GenOptions, LLMClient

from pageindex_test.db.repos import ChunkRepo, utcnow
from pageindex_test.db.schema import query_traces
from pageindex_test.obs.trace import TraceRecorder, bind_trace
from pageindex_test.retrieval.fusion import reciprocal_rank_fusion
from pageindex_test.retrieval.lexical import LexicalIndex

logger = logging.getLogger("pageindex_test.pipeline")

ANSWER_SYSTEM = (
    "You are a precise assistant answering from the user's own documents. "
    "Answer concisely and only from the provided context. When the context "
    "does not contain the answer, say so plainly."
)

_ANSWER_TEMPLATE = """Use the following document excerpts to answer the question.

{context}

Question: {question}

Answer concisely using only the excerpts above."""


@dataclass(frozen=True)
class Citation:
    doc_id: str
    chunk_id: str | None
    heading: str
    snippet: str

    def as_dict(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "chunk_id": self.chunk_id,
            "heading": self.heading,
            "snippet": self.snippet,
        }


@dataclass
class QueryResult:
    answer: str
    citations: list[Citation]
    trace_id: str
    pipeline: str
    total_ms: float
    stages: list[dict] = field(default_factory=list)


class QueryPipeline:
    def __init__(
        self,
        engine,
        chunks: ChunkRepo,
        lexical: LexicalIndex,
        embedder: EmbeddingClient,
        vector_index_factory,
        llm: LLMClient,
        *,
        hybrid_top_n: int = 8,
        tree_stage=None,  # Phase 5: TreeStage | None
    ) -> None:
        self._engine = engine
        self._chunks = chunks
        self._lexical = lexical
        self._embedder = embedder
        self._vector_index_factory = vector_index_factory
        self._llm = llm
        self._hybrid_top_n = hybrid_top_n
        self._tree_stage = tree_stage

    def ask(
        self,
        location_id: str,
        question: str,
        model: str,
        *,
        use_pageindex_stage: bool = True,
    ) -> QueryResult:
        recorder = TraceRecorder()
        pipeline_name = (
            "staged" if (use_pageindex_stage and self._tree_stage is not None) else "hybrid_only"
        )
        prompt_tokens = completion_tokens = llm_calls = 0

        with bind_trace(recorder):
            with recorder.stage("bm25") as stage:
                lexical_hits = self._lexical.search(question, self._hybrid_top_n * 2)
                stage.candidates = len(lexical_hits)

            with recorder.stage("vector") as stage:
                [query_vector] = self._embedder.embed([question])
                vector_hits = self._vector_index_factory(location_id).search(
                    query_vector, self._hybrid_top_n * 2
                )
                stage.candidates = len(vector_hits)

            with recorder.stage("fusion") as stage:
                fused = reciprocal_rank_fusion(lexical_hits, vector_hits, limit=self._hybrid_top_n)
                stage.candidates = len(fused)
                stage.detail = {"chunk_ids": [hit.chunk_id for hit in fused][:20]}

            citations: list[Citation]
            context = ""
            if pipeline_name == "staged":
                from pageindex_test.retrieval.trees import TreeStageOverBudget

                try:
                    tree_result = self._tree_stage.run(
                        recorder, location_id, question, model, fused
                    )
                    context = tree_result.context
                    citations = tree_result.citations
                    prompt_tokens += tree_result.prompt_tokens
                    completion_tokens += tree_result.completion_tokens
                    llm_calls += tree_result.llm_calls
                except TreeStageOverBudget as exc:
                    # NEVER silently truncate: fall back to hybrid context and
                    # record why, visibly, in the trace
                    logger.warning("tree stage fallback", extra={"data": {"reason": str(exc)}})
                    with recorder.stage("tree_fallback") as stage:
                        stage.detail = {"reason": str(exc)}
                    pipeline_name = "hybrid_only"
            if pipeline_name == "hybrid_only":
                chunk_rows = self._chunks.get_many([hit.chunk_id for hit in fused])
                context = "\n\n---\n\n".join(
                    f"[{row['heading_path'] or row['doc_id']}]\n{row['text']}" for row in chunk_rows
                )
                citations = [
                    Citation(
                        doc_id=row["doc_id"],
                        chunk_id=row["id"],
                        heading=row["heading_path"] or "",
                        snippet=row["text"][:240],
                    )
                    for row in chunk_rows
                ]

            with recorder.stage("answer") as stage:
                response = self._llm.generate(
                    model,
                    _ANSWER_TEMPLATE.format(context=context, question=question),
                    system=ANSWER_SYSTEM,
                    options=GenOptions(),
                )
                stage.tokens = response.prompt_tokens + response.completion_tokens
                stage.detail = {"model": model, "tokens_per_sec": round(response.tokens_per_sec, 1)}
                prompt_tokens += response.prompt_tokens
                completion_tokens += response.completion_tokens
                llm_calls += 1

        result = QueryResult(
            answer=response.text.strip(),
            citations=citations,
            trace_id=recorder.trace_id,
            pipeline=pipeline_name,
            total_ms=recorder.total_ms,
            stages=recorder.stages_json(),
        )
        self._persist_trace(
            recorder,
            location_id,
            question,
            model,
            pipeline_name,
            result,
            prompt_tokens,
            completion_tokens,
            llm_calls,
        )
        logger.info(
            "query answered",
            extra={
                "data": {
                    "pipeline": pipeline_name,
                    "model": model,
                    "total_ms": round(recorder.total_ms),
                    "llm_calls": llm_calls,
                }
            },
        )
        return result

    def _persist_trace(
        self,
        recorder: TraceRecorder,
        location_id: str,
        question: str,
        model: str,
        pipeline_name: str,
        result: QueryResult,
        prompt_tokens: int,
        completion_tokens: int,
        llm_calls: int,
    ) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                query_traces.insert().values(
                    trace_id=recorder.trace_id,
                    location_id=location_id,
                    question=question,
                    model=model,
                    pipeline=pipeline_name,
                    stages=result.stages,
                    total_ms=recorder.total_ms,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    llm_calls=llm_calls,
                    answer=result.answer,
                    sources=[c.as_dict() for c in result.citations],
                    created_at=utcnow(),
                )
            )
