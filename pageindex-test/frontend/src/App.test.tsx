import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import App from "./App";
import { renderWithProviders } from "./test/render";
import { metaFixture, server } from "./test/server";

describe("App shell", () => {
  it("renders nav and redirects / to chat", async () => {
    renderWithProviders(<App />);
    expect(screen.getByText(/PAGEINDEX/)).toBeInTheDocument();
    for (const label of ["Chat", "Documents", "Eval", "Logs", "Settings"]) {
      expect(screen.getByRole("link", { name: new RegExp(label) })).toBeInTheDocument();
    }
    expect(await screen.findByRole("heading", { name: "Chat" })).toBeInTheDocument();
  });

  it("shows green health checks from /api/meta", async () => {
    renderWithProviders(<App />);
    expect(await screen.findByText("database")).toBeInTheDocument();
    expect(screen.getByText("qdrant")).toBeInTheDocument();
    expect(screen.getByText("ollama")).toBeInTheDocument();
    expect(screen.queryByText("offline")).not.toBeInTheDocument();
  });

  it("flags failing checks as offline", async () => {
    server.use(
      http.get("/api/meta", () =>
        HttpResponse.json({
          ...metaFixture,
          ok: false,
          checks: { ...metaFixture.checks, ollama: { ok: false, error: "refused" } },
        }),
      ),
    );
    renderWithProviders(<App />);
    expect(await screen.findByText("offline")).toBeInTheDocument();
  });
});
