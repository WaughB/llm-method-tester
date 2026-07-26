export function fmtScore(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(2);
}

export function fmtPct(value: number | null | undefined): string {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

export function fmtLatency(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function fmtTps(value: number | null | undefined): string {
  return value == null ? "—" : `${value.toFixed(1)} tok/s`;
}

/** "gpt-oss:20b" -> "gpt-oss", keeps the tag as detail when needed */
export function modelShort(model: string): string {
  return model.split(":")[0];
}

export const STRATEGY_LABELS: Record<string, string> = {
  baseline: "Baseline",
  traditional_rag: "Vector RAG",
  obsidian_rag: "Obsidian RAG",
  pageindex: "PageIndex (reimpl)",
  pageindex_official: "PageIndex (official)",
};

export function strategyLabel(name: string): string {
  return STRATEGY_LABELS[name] ?? name;
}

export const CATEGORY_LABELS: Record<string, string> = {
  single_hop: "Single-hop",
  multi_hop: "Multi-hop",
  aggregation: "Aggregation",
};
