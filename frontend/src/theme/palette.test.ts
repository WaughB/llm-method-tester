import { describe, expect, it } from "vitest";
import { heatColor, modelColor } from "./palette";

describe("modelColor", () => {
  it("is stable per model regardless of query order", () => {
    const first = modelColor("model-alpha");
    modelColor("model-beta");
    expect(modelColor("model-alpha")).toBe(first);
  });

  it("assigns distinct colors to distinct models", () => {
    expect(modelColor("model-alpha")).not.toBe(modelColor("model-beta"));
  });
});

describe("heatColor", () => {
  it("returns the neutral cell color for null", () => {
    expect(heatColor(null)).toBe("#2c2c2a");
  });

  it("maps low scores to darker steps than high scores", () => {
    expect(heatColor(0)).not.toBe(heatColor(5));
  });

  it("clamps out-of-range scores", () => {
    expect(heatColor(99)).toBe(heatColor(5));
    expect(heatColor(-3)).toBe(heatColor(0));
  });
});
