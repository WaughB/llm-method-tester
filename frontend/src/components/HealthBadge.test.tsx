import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../test/render";
import { server } from "../test/server";
import { HealthBadge } from "./HealthBadge";

describe("HealthBadge", () => {
  it("reports Ollama online with model count", async () => {
    renderWithProviders(<HealthBadge />);
    expect(await screen.findByText("Ollama online")).toBeInTheDocument();
    expect(screen.getByText("3 models")).toBeInTheDocument();
  });

  it("reports Ollama offline", async () => {
    server.use(
      http.get("/api/health", () =>
        HttpResponse.json({ ok: false, models: [], error: "refused" }),
      ),
    );
    renderWithProviders(<HealthBadge />);
    expect(await screen.findByText("Ollama offline")).toBeInTheDocument();
  });
});
