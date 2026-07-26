import type { Health, Meta, Question, ResultRow, Run, SummaryRow } from "./types";

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`GET ${path} -> ${response.status}`);
  return response.json() as Promise<T>;
}

export const api = {
  health: () => get<Health>("/api/health"),
  meta: () => get<Meta>("/api/meta"),
  questions: () => get<Question[]>("/api/questions"),
  runs: () => get<Run[]>("/api/runs"),
  run: (id: number) => get<Run>(`/api/runs/${id}`),
  results: (id: number) => get<ResultRow[]>(`/api/runs/${id}/results`),
  summary: (id: number, category?: string) =>
    get<SummaryRow[]>(
      category ? `/api/runs/${id}/summary?category=${category}` : `/api/runs/${id}/summary`,
    ),
  startRun: async (body: {
    models?: string[];
    strategies?: string[];
    question_ids?: string[];
  }): Promise<{ run_id: number }> => {
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (response.status === 409) throw new Error("A run is already in progress");
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail ?? `POST /api/runs -> ${response.status}`);
    }
    return response.json();
  },
};
