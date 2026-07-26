// Mirrors the FastAPI response schemas.

export type Category = "single_hop" | "multi_hop" | "aggregation";

export interface Question {
  id: string;
  question: string;
  category: Category;
  expected_keywords: string[][];
  source_docs: string[];
  source_notes: string[];
  gold_answer: string;
}

export interface Meta {
  models: string[];
  strategies: string[];
  question_count: number;
}

export interface Health {
  ok: boolean;
  models: string[];
  error?: string;
}

export interface RunProgress {
  total: number;
  done: number;
  current: string;
}

export interface Run {
  id: number;
  started_at: string;
  finished_at: string | null;
  status: "running" | "completed" | "failed";
  config: {
    models?: string[];
    strategies?: string[];
    question_ids?: string[];
  };
  error: string | null;
  progress?: RunProgress | null;
}

export interface ResultRow {
  id: number | null;
  run_id: number;
  model: string;
  strategy: string;
  question_id: string;
  category: Category;
  answer: string;
  retrieved_ids: string[];
  latency_ms: number;
  tokens_per_sec: number;
  llm_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  context_chars: number;
  keyword_recall: number;
  retrieval_hit_rate: number | null;
  judge_score: number | null;
  judge_verdict: string | null;
  judge_reasoning: string | null;
  error: string | null;
}

export interface SummaryRow {
  model: string;
  strategy: string;
  count: number;
  error_count: number;
  avg_judge_score: number | null;
  avg_keyword_recall: number | null;
  avg_retrieval_hit_rate: number | null;
  avg_latency_ms: number | null;
  avg_tokens_per_sec: number | null;
  avg_llm_calls: number | null;
}
