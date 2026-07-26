// Validated dark-surface categorical slots (all-pairs safe for three series).
// Color follows the MODEL (the entity), fixed by assignment order — never rank.
const MODEL_SLOTS = ["#3987e5", "#d95926", "#199e70"];
const FALLBACK = "#9085e9";

const assigned = new Map<string, string>();

export function modelColor(model: string): string {
  if (!assigned.has(model)) {
    assigned.set(model, MODEL_SLOTS[assigned.size] ?? FALLBACK);
  }
  return assigned.get(model)!;
}

/** Sequential blue ramp (ordinal band, dark surface) for the score heatmap. */
const SEQ = ["#0d366b", "#104281", "#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5"];

export function heatColor(score: number | null, max = 5): string {
  if (score == null) return "#2c2c2a";
  const t = Math.max(0, Math.min(1, score / max));
  return SEQ[Math.round(t * (SEQ.length - 1))];
}

export const CHART_INK = {
  muted: "#898781",
  grid: "#2c2c2a",
  baseline: "#383835",
  ink: "#ffffff",
  sub: "#c3c2b7",
  surface: "#1a1a19",
};
