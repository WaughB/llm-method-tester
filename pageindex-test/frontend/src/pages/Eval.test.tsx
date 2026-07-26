import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../test/render";
import { server } from "../test/server";
import Eval from "./Eval";

const setSummary = { id: "s1", name: "smoke", question_count: 2, approved_count: 1 };

const detail = {
  ...setSummary,
  questions: [
    {
      id: "q1",
      question: "Which port?",
      expected_keywords: [["7433"]],
      gold_doc_ids: ["d1"],
      source: "manual",
      approved: true,
    },
    {
      id: "q2",
      question: "Generated one?",
      expected_keywords: [["x"]],
      gold_doc_ids: ["d2"],
      source: "generated",
      approved: false,
    },
  ],
  runs: [
    {
      id: "r1",
      model: "llama3.1:8b",
      pipeline: "staged",
      status: "done",
      summary: { count: 1, avg_keyword_recall: 0.9, avg_retrieval_hit: 0.8, avg_judge_score: 4.5 },
    },
    {
      id: "r2",
      model: "llama3.1:8b",
      pipeline: "hybrid_only",
      status: "done",
      summary: { count: 1, avg_keyword_recall: 0.7, avg_retrieval_hit: 0.6, avg_judge_score: 3.9 },
    },
  ],
};

function useEvalHandlers() {
  server.use(
    http.get("/api/eval-sets", () => HttpResponse.json({ sets: [setSummary] })),
    http.get("/api/eval-sets/s1", () => HttpResponse.json(detail)),
  );
}

describe("Eval", () => {
  it("lists sets and shows questions with approval state", async () => {
    useEvalHandlers();
    const user = userEvent.setup();
    renderWithProviders(<Eval />);
    await user.click(await screen.findByText("smoke"));
    expect(await screen.findByText("Which port?")).toBeInTheDocument();
    expect(screen.getByText("approved")).toBeInTheDocument();
    expect(screen.getByText("approve?")).toBeInTheDocument();
  });

  it("renders the staged vs hybrid comparison tiles", async () => {
    useEvalHandlers();
    const user = userEvent.setup();
    renderWithProviders(<Eval />);
    await user.click(await screen.findByText("smoke"));
    expect(await screen.findByText("4.50")).toBeInTheDocument(); // staged judge
    expect(screen.getByText("3.90")).toBeInTheDocument(); // hybrid judge
    expect(screen.getByText("80%")).toBeInTheDocument(); // staged hit
    expect(screen.getByText("60%")).toBeInTheDocument(); // hybrid hit
  });

  it("launches a comparison run pair", async () => {
    useEvalHandlers();
    let launched = false;
    server.use(
      http.post("/api/eval-sets/s1/runs", () => {
        launched = true;
        return HttpResponse.json({ runs: [] }, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<Eval />);
    await user.click(await screen.findByText("smoke"));
    await user.click(await screen.findByText("RUN STAGED VS HYBRID →"));
    expect(launched).toBe(true);
  });

  it("toggles question approval", async () => {
    useEvalHandlers();
    let approvedBody: unknown = null;
    server.use(
      http.put("/api/eval-questions/q2/approved", async ({ request }) => {
        approvedBody = await request.json();
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<Eval />);
    await user.click(await screen.findByText("smoke"));
    await user.click(await screen.findByText("approve?"));
    expect(approvedBody).toEqual({ approved: true });
  });
});
