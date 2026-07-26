"""Full schema, SQLAlchemy Core. Portable across Postgres (runtime) and
SQLite (tests): JSON columns are sqlalchemy.JSON, timestamps are ISO strings.
`init_schema` is idempotent — applied at every startup, no migrations."""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Engine,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
)

metadata = MetaData()

app_settings = Table(
    "app_settings",
    metadata,
    Column("key", String(64), primary_key=True),
    Column("value", JSON, nullable=False),
)

documents = Table(
    "documents",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("location_id", String(12), nullable=False, index=True),
    Column("filename", Text, nullable=False),
    Column("format", String(8), nullable=False),  # pdf | md | txt
    Column("status", String(16), nullable=False),  # pending|processing|ready|unsupported|error
    Column("error", Text),
    Column("title", Text),
    Column("pages", Integer),
    Column("chunk_count", Integer),
    Column("content_sha256", String(64)),
    Column("created_at", String(32), nullable=False),
)

chunks = Table(
    "chunks",
    metadata,
    Column("id", String(64), primary_key=True),  # "<doc_id>#<ordinal>"
    Column("doc_id", String(36), ForeignKey("documents.id"), nullable=False, index=True),
    Column("location_id", String(12), nullable=False, index=True),
    Column("ordinal", Integer, nullable=False),
    Column("heading_path", Text),
    Column("text", Text, nullable=False),
    Column("token_estimate", Integer, nullable=False),
)

jobs = Table(
    "jobs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("location_id", String(12), nullable=False),
    Column("type", String(24), nullable=False),  # ingest | eval_run
    Column("payload", JSON, nullable=False),
    Column("status", String(12), nullable=False, index=True),  # queued|running|done|error
    Column("error", Text),
    Column("attempts", Integer, nullable=False, default=0),
    Column("created_at", String(32), nullable=False),
    Column("started_at", String(32)),
    Column("finished_at", String(32)),
)

conversations = Table(
    "conversations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("location_id", String(12), nullable=False, index=True),
    Column("title", Text, nullable=False),
    Column("model", String(64), nullable=False),
    Column("use_pageindex_stage", Boolean, nullable=False, default=True),
    Column("created_at", String(32), nullable=False),
)

messages = Table(
    "messages",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "conversation_id", String(36), ForeignKey("conversations.id"), nullable=False, index=True
    ),
    Column("role", String(12), nullable=False),  # user | assistant
    Column("content", Text, nullable=False),
    Column("citations", JSON),
    Column("trace_id", String(36)),
    Column("created_at", String(32), nullable=False),
)

query_traces = Table(
    "query_traces",
    metadata,
    Column("trace_id", String(36), primary_key=True),
    Column("location_id", String(12), nullable=False),
    Column("question", Text, nullable=False),
    Column("model", String(64), nullable=False),
    Column("pipeline", String(16), nullable=False),  # staged | hybrid_only
    Column("stages", JSON, nullable=False),  # [{name, ms, candidates, tokens, detail}]
    Column("total_ms", Float, nullable=False),
    Column("prompt_tokens", Integer, nullable=False),
    Column("completion_tokens", Integer, nullable=False),
    Column("llm_calls", Integer, nullable=False),
    Column("answer", Text, nullable=False),
    Column("sources", JSON, nullable=False),
    Column("created_at", String(32), nullable=False, index=True),
)

logs = Table(
    "logs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ts", String(32), nullable=False),
    Column("level", String(10), nullable=False),
    Column("component", String(48), nullable=False),
    Column("message", Text, nullable=False),
    Column("trace_id", String(36)),
    Column("data", JSON),
)
Index("ix_logs_ts", logs.c.ts)
Index("ix_logs_level", logs.c.level)
Index("ix_logs_trace", logs.c.trace_id)

eval_sets = Table(
    "eval_sets",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("location_id", String(12), nullable=False, index=True),
    Column("name", Text, nullable=False),
    Column("created_at", String(32), nullable=False),
)

eval_questions = Table(
    "eval_questions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("set_id", String(36), ForeignKey("eval_sets.id"), nullable=False, index=True),
    Column("question", Text, nullable=False),
    Column("expected_keywords", JSON, nullable=False),  # list[list[str]] alias groups
    Column("gold_doc_ids", JSON, nullable=False),
    Column("source", String(12), nullable=False),  # manual | generated
    Column("approved", Boolean, nullable=False, default=True),
)

eval_runs = Table(
    "eval_runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("set_id", String(36), ForeignKey("eval_sets.id"), nullable=False, index=True),
    Column("model", String(64), nullable=False),
    Column("pipeline", String(16), nullable=False),
    Column("status", String(12), nullable=False),  # queued|running|done|error
    Column("started_at", String(32)),
    Column("finished_at", String(32)),
    Column("summary", JSON),
)

eval_results = Table(
    "eval_results",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String(36), ForeignKey("eval_runs.id"), nullable=False, index=True),
    Column("question_id", String(36), ForeignKey("eval_questions.id"), nullable=False),
    Column("answer", Text, nullable=False),
    Column("keyword_recall", Float, nullable=False),
    Column("retrieval_hit", Float),
    Column("judge_score", Integer),
    Column("judge_rationale", Text),
    Column("trace_id", String(36)),
)


def make_engine(database_url: str) -> Engine:
    return create_engine(database_url, future=True)


def init_schema(engine: Engine) -> None:
    """Create any missing tables. Safe to call on every startup."""
    metadata.create_all(engine)
