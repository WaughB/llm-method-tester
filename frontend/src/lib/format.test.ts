import { describe, expect, it } from "vitest";
import { fmtLatency, fmtPct, fmtScore, fmtTps, modelShort, strategyLabel } from "./format";

describe("fmtScore", () => {
  it("formats numbers to two decimals", () => expect(fmtScore(3.14159)).toBe("3.14"));
  it("renders em dash for null", () => expect(fmtScore(null)).toBe("—"));
  it("renders em dash for undefined", () => expect(fmtScore(undefined)).toBe("—"));
});

describe("fmtPct", () => {
  it("rounds to whole percent", () => expect(fmtPct(0.856)).toBe("86%"));
  it("handles zero", () => expect(fmtPct(0)).toBe("0%"));
  it("renders em dash for null", () => expect(fmtPct(null)).toBe("—"));
});

describe("fmtLatency", () => {
  it("uses ms under a second", () => expect(fmtLatency(420)).toBe("420ms"));
  it("uses seconds above a second", () => expect(fmtLatency(9800)).toBe("9.8s"));
  it("renders em dash for null", () => expect(fmtLatency(null)).toBe("—"));
});

describe("fmtTps", () => {
  it("formats tokens per second", () => expect(fmtTps(41.27)).toBe("41.3 tok/s"));
});

describe("modelShort", () => {
  it("strips the tag", () => expect(modelShort("gpt-oss:20b")).toBe("gpt-oss"));
  it("passes through untagged names", () => expect(modelShort("plain")).toBe("plain"));
});

describe("strategyLabel", () => {
  it("maps known strategies", () => expect(strategyLabel("traditional_rag")).toBe("Vector RAG"));
  it("falls back to the raw name", () => expect(strategyLabel("mystery")).toBe("mystery"));
});
