import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";
import { renderWithProviders } from "./test/render";

describe("App shell", () => {
  it("renders the wordmark, nav, and redirects / to the dashboard", async () => {
    renderWithProviders(<App />, { route: "/" });
    expect(screen.getByText(/LLM·METHOD/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /New run/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Runs/ })).toBeInTheDocument();
    // redirect landed on the dashboard page
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
  });
});
