import type { SummaryRow } from "../api/types";

/** One x-axis group per strategy, one keyed value per model — Recharts shape. */
export interface StrategyGroup {
  strategy: string;
  [model: string]: string | number | null;
}

export function groupByStrategy(
  rows: SummaryRow[],
  metric: keyof SummaryRow,
): StrategyGroup[] {
  const strategies = [...new Set(rows.map((r) => r.strategy))];
  return strategies.map((strategy) => {
    const group: StrategyGroup = { strategy };
    for (const row of rows.filter((r) => r.strategy === strategy)) {
      group[row.model] = row[metric] as number | null;
    }
    return group;
  });
}

export function modelsIn(rows: SummaryRow[]): string[] {
  return [...new Set(rows.map((r) => r.model))];
}

export function strategiesIn(rows: SummaryRow[]): string[] {
  return [...new Set(rows.map((r) => r.strategy))];
}

export interface Headline {
  bestStrategy: string | null;
  bestStrategyScore: number | null;
  fastestStrategy: string | null;
  fastestLatencyMs: number | null;
  bestBaselineGap: number | null; // best strategy score minus baseline score
}

/** Averages a metric across models for each strategy (null-safe). */
export function strategyMeans(
  rows: SummaryRow[],
  metric: keyof SummaryRow,
): Map<string, number> {
  const sums = new Map<string, { total: number; n: number }>();
  for (const row of rows) {
    const value = row[metric];
    if (typeof value !== "number") continue;
    const entry = sums.get(row.strategy) ?? { total: 0, n: 0 };
    entry.total += value;
    entry.n += 1;
    sums.set(row.strategy, entry);
  }
  return new Map([...sums].map(([k, v]) => [k, v.total / v.n]));
}

export function computeHeadline(rows: SummaryRow[]): Headline {
  const scores = strategyMeans(rows, "avg_judge_score");
  const latencies = strategyMeans(rows, "avg_latency_ms");
  let bestStrategy: string | null = null;
  let bestStrategyScore: number | null = null;
  for (const [strategy, score] of scores) {
    if (bestStrategyScore == null || score > bestStrategyScore) {
      bestStrategy = strategy;
      bestStrategyScore = score;
    }
  }
  let fastestStrategy: string | null = null;
  let fastestLatencyMs: number | null = null;
  for (const [strategy, latency] of latencies) {
    if (fastestLatencyMs == null || latency < fastestLatencyMs) {
      fastestStrategy = strategy;
      fastestLatencyMs = latency;
    }
  }
  const baseline = scores.get("baseline");
  const bestBaselineGap =
    bestStrategyScore != null && baseline != null ? bestStrategyScore - baseline : null;
  return { bestStrategy, bestStrategyScore, fastestStrategy, fastestLatencyMs, bestBaselineGap };
}
