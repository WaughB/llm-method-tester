import { describe, expect, it } from "vitest";
import { summary, summaryRow } from "../test/fixtures";
import { computeHeadline, groupByStrategy, modelsIn, strategyMeans } from "./aggregate";

describe("groupByStrategy", () => {
  it("produces one group per strategy keyed by model", () => {
    const rows = [
      summaryRow({ model: "m1", strategy: "baseline", avg_judge_score: 1 }),
      summaryRow({ model: "m2", strategy: "baseline", avg_judge_score: 2 }),
      summaryRow({ model: "m1", strategy: "pageindex", avg_judge_score: 4 }),
    ];
    const groups = groupByStrategy(rows, "avg_judge_score");
    expect(groups).toHaveLength(2);
    expect(groups[0]).toEqual({ strategy: "baseline", m1: 1, m2: 2 });
    expect(groups[1]).toEqual({ strategy: "pageindex", m1: 4 });
  });
});

describe("modelsIn", () => {
  it("dedupes preserving order", () => {
    const rows = [
      summaryRow({ model: "a" }),
      summaryRow({ model: "b" }),
      summaryRow({ model: "a" }),
    ];
    expect(modelsIn(rows)).toEqual(["a", "b"]);
  });
});

describe("strategyMeans", () => {
  it("averages across models and skips nulls", () => {
    const rows = [
      summaryRow({ model: "m1", strategy: "s", avg_judge_score: 2 }),
      summaryRow({ model: "m2", strategy: "s", avg_judge_score: 4 }),
      summaryRow({ model: "m3", strategy: "s", avg_judge_score: null }),
    ];
    expect(strategyMeans(rows, "avg_judge_score").get("s")).toBe(3);
  });
});

describe("computeHeadline", () => {
  it("finds best and fastest strategies and the baseline gap", () => {
    const headline = computeHeadline(summary);
    expect(headline.bestStrategy).toBe("obsidian_rag");
    expect(headline.bestStrategyScore).toBeCloseTo(4.4);
    expect(headline.fastestStrategy).toBe("baseline");
    expect(headline.bestBaselineGap).toBeCloseTo(3.9);
  });

  it("handles empty input", () => {
    const headline = computeHeadline([]);
    expect(headline.bestStrategy).toBeNull();
    expect(headline.fastestLatencyMs).toBeNull();
    expect(headline.bestBaselineGap).toBeNull();
  });
});
