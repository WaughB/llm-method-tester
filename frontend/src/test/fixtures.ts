import type { Question, ResultRow, Run, SummaryRow } from "../api/types";

export const MODELS = ["gpt-oss:20b", "nemotron-3-nano:4b", "llama3.1:8b"];
export const STRATEGIES = ["baseline", "traditional_rag", "obsidian_rag", "pageindex"];

export const completedRun: Run = {
  id: 7,
  started_at: "2026-07-25T20:00:00Z",
  finished_at: "2026-07-25T22:00:00Z",
  status: "completed",
  config: { models: MODELS, strategies: STRATEGIES, question_ids: ["sh-01", "mh-01"] },
  error: null,
};

export const runningRun: Run = {
  ...completedRun,
  id: 8,
  status: "running",
  finished_at: null,
  progress: { total: 24, done: 6, current: "llama3.1:8b / baseline / sh-03" },
};

export function summaryRow(overrides: Partial<SummaryRow>): SummaryRow {
  return {
    model: "gpt-oss:20b",
    strategy: "baseline",
    count: 2,
    error_count: 0,
    avg_judge_score: 1.0,
    avg_keyword_recall: 0.2,
    avg_retrieval_hit_rate: null,
    avg_latency_ms: 2500,
    avg_tokens_per_sec: 40,
    avg_llm_calls: 1,
    ...overrides,
  };
}

export const summary: SummaryRow[] = [
  summaryRow({ strategy: "baseline", avg_judge_score: 0.5 }),
  summaryRow({
    strategy: "traditional_rag",
    avg_judge_score: 4.1,
    avg_retrieval_hit_rate: 0.9,
    avg_latency_ms: 4200,
  }),
  summaryRow({
    strategy: "obsidian_rag",
    avg_judge_score: 4.4,
    avg_retrieval_hit_rate: 0.95,
    avg_latency_ms: 3900,
  }),
  summaryRow({
    strategy: "pageindex",
    avg_judge_score: 3.8,
    avg_retrieval_hit_rate: 0.8,
    avg_latency_ms: 9800,
    avg_llm_calls: 3,
  }),
];

export const questions: Question[] = [
  {
    id: "sh-01",
    question: "What TCP port does the Aurora Mesh control plane listen on?",
    category: "single_hop",
    expected_keywords: [["7433"]],
    source_docs: ["docs/configuration.md"],
    source_notes: ["vault/Reference/Ports.md"],
    gold_answer: "The control plane listens on TCP port 7433.",
  },
  {
    id: "mh-01",
    question: "Which gossip protocol runs on which UDP port?",
    category: "multi_hop",
    expected_keywords: [["glowcast"], ["7434"]],
    source_docs: ["docs/architecture.md"],
    source_notes: ["vault/Concepts/Glowcast.md"],
    gold_answer: "The glowcast gossip protocol runs on UDP 7434.",
  },
];

export function resultRow(overrides: Partial<ResultRow>): ResultRow {
  return {
    id: 1,
    run_id: 7,
    model: "gpt-oss:20b",
    strategy: "traditional_rag",
    question_id: "sh-01",
    category: "single_hop",
    answer: "The control plane listens on port 7433.",
    retrieved_ids: ["docs/configuration.md"],
    latency_ms: 3200,
    tokens_per_sec: 55,
    llm_calls: 1,
    prompt_tokens: 900,
    completion_tokens: 40,
    context_chars: 3000,
    keyword_recall: 1.0,
    retrieval_hit_rate: 1.0,
    judge_score: 5,
    judge_verdict: "correct",
    judge_reasoning: "Matches the gold answer exactly.",
    error: null,
    ...overrides,
  };
}

export const results: ResultRow[] = [
  resultRow({ id: 1 }),
  resultRow({
    id: 2,
    strategy: "baseline",
    answer: "I do not know of a system called Aurora Mesh.",
    retrieved_ids: [],
    keyword_recall: 0,
    retrieval_hit_rate: null,
    judge_score: 0,
    judge_verdict: "incorrect",
    judge_reasoning: "No relevant facts.",
  }),
  resultRow({
    id: 3,
    question_id: "mh-01",
    category: "multi_hop",
    strategy: "pageindex",
    llm_calls: 3,
    retrieved_ids: ["docs/architecture.md", "docs/overview.md"],
  }),
];
