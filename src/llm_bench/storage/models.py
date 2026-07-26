"""Typed records for runs, results, and summary rows."""

from pydantic import BaseModel


class RunRecord(BaseModel):
    id: int
    started_at: str
    finished_at: str | None = None
    status: str  # running | completed | failed
    config: dict
    error: str | None = None


class ResultRecord(BaseModel):
    run_id: int
    model: str
    strategy: str
    question_id: str
    category: str
    answer: str
    retrieved_ids: list[str]
    latency_ms: float
    tokens_per_sec: float
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    context_chars: int
    keyword_recall: float
    retrieval_hit_rate: float | None = None
    judge_score: int | None = None
    judge_verdict: str | None = None
    judge_reasoning: str | None = None
    error: str | None = None


class SummaryRow(BaseModel):
    model: str
    strategy: str
    count: int
    error_count: int
    avg_judge_score: float | None = None
    avg_keyword_recall: float | None = None
    avg_retrieval_hit_rate: float | None = None
    avg_latency_ms: float | None = None
    avg_tokens_per_sec: float | None = None
    avg_llm_calls: float | None = None
