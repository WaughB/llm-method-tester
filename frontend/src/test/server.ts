import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { completedRun, MODELS, questions, results, STRATEGIES, summary } from "./fixtures";

export const handlers = [
  http.get("/api/health", () => HttpResponse.json({ ok: true, models: MODELS })),
  http.get("/api/meta", () =>
    HttpResponse.json({ models: MODELS, strategies: STRATEGIES, question_count: 30 }),
  ),
  http.get("/api/questions", () => HttpResponse.json(questions)),
  http.get("/api/runs", () => HttpResponse.json([completedRun])),
  http.get("/api/runs/7", () => HttpResponse.json(completedRun)),
  http.get("/api/runs/7/results", () => HttpResponse.json(results)),
  http.get("/api/runs/7/summary", () => HttpResponse.json(summary)),
  http.post("/api/runs", () => HttpResponse.json({ run_id: 9 }, { status: 202 })),
];

export const server = setupServer(...handlers);
