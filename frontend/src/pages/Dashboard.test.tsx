import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../test/render";
import { server } from "../test/server";
import Dashboard from "./Dashboard";

describe("Dashboard", () => {
  it("shows headline tiles from the latest completed run", async () => {
    renderWithProviders(<Dashboard />);
    expect(await screen.findByText("best strategy")).toBeInTheDocument();
    // obsidian_rag has the highest judge score in the fixture summary
    expect(await screen.findAllByText("Obsidian RAG")).not.toHaveLength(0);
    expect(screen.getByText("run #7 · " + new Date("2026-07-25T20:00:00Z").toLocaleString())).toBeInTheDocument();
  });

  it("renders the four metric chart sections and the heatmap", async () => {
    renderWithProviders(<Dashboard />);
    expect(await screen.findByText("Judge score (0–5)")).toBeInTheDocument();
    expect(screen.getByText("Keyword recall")).toBeInTheDocument();
    expect(screen.getByText("Retrieval hit rate")).toBeInTheDocument();
    expect(screen.getByText("Latency per question")).toBeInTheDocument();
    expect(screen.getByText("Judge score, model × strategy")).toBeInTheDocument();
  });

  it("offers a start-run link when no runs exist", async () => {
    server.use(http.get("/api/runs", () => HttpResponse.json([])));
    renderWithProviders(<Dashboard />);
    expect(await screen.findByText(/START A RUN/)).toBeInTheDocument();
  });
});
