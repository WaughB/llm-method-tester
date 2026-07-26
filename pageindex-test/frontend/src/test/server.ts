import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type { Meta } from "../api/types";

export const metaFixture: Meta = {
  version: "0.1.0",
  default_model: "llama3.1:8b",
  ok: true,
  checks: {
    database: { ok: true },
    qdrant: { ok: true },
    ollama: { ok: true, models: ["llama3.1:8b", "nomic-embed-text:latest"] },
  },
};

export const handlers = [
  http.get("/api/meta", () => HttpResponse.json(metaFixture)),
  http.get("/api/conversations", () => HttpResponse.json({ conversations: [] })),
];

export const server = setupServer(...handlers);
