import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../test/render";
import { server } from "../test/server";
import Logs from "./Logs";

const rows = [
  {
    id: 2,
    ts: "2026-07-26T20:11:04+00:00",
    level: "WARNING",
    component: "pageindex_test.trees",
    message: "tree stage fallback",
    trace_id: "trace-1234-abcd-9999",
    data: { reason: "over budget" },
  },
  {
    id: 1,
    ts: "2026-07-26T20:10:00+00:00",
    level: "INFO",
    component: "pageindex_test.pipeline",
    message: "query answered",
    trace_id: null,
    data: null,
  },
];

const trace = {
  trace_id: "trace-1234-abcd-9999",
  question: "Which port?",
  model: "llama3.1:8b",
  pipeline: "staged",
  total_ms: 4200,
  prompt_tokens: 900,
  completion_tokens: 60,
  llm_calls: 2,
  answer: "7433",
  stages: [
    { name: "bm25", ms: 3, candidates: 8, tokens: 0 },
    { name: "tree_select", ms: 2100, candidates: 2, tokens: 800 },
    { name: "answer", ms: 2000, candidates: 0, tokens: 160 },
  ],
};

function useLogHandlers() {
  server.use(
    http.get("/api/logs", () => HttpResponse.json({ logs: rows, total: 2 })),
    http.get("/api/traces/trace-1234-abcd-9999", () => HttpResponse.json(trace)),
  );
}

describe("Logs", () => {
  it("renders log rows with levels and data", async () => {
    useLogHandlers();
    renderWithProviders(<Logs />);
    expect(await screen.findByText("tree stage fallback")).toBeInTheDocument();
    // WARNING appears both as a filter option and the row's level cell
    expect(screen.getAllByText("WARNING").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/over budget/)).toBeInTheDocument();
    expect(screen.getByText("2 rows")).toBeInTheDocument();
  });

  it("clicking a trace id loads the waterfall", async () => {
    useLogHandlers();
    const user = userEvent.setup();
    renderWithProviders(<Logs />);
    await user.click(await screen.findByRole("button", { name: "trace-12" }));
    expect(await screen.findByText("trace waterfall")).toBeInTheDocument();
    expect(screen.getByText("tree_select")).toBeInTheDocument();
    expect(screen.getByText(/2100ms/)).toBeInTheDocument();
    expect(screen.getByText(/staged · llama3\.1:8b/)).toBeInTheDocument();
  });
});
