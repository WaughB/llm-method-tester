import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { completedRun, runningRun } from "../test/fixtures";
import { renderWithProviders } from "../test/render";
import { server } from "../test/server";
import Runs from "./Runs";

describe("Runs", () => {
  it("lists runs with status chips and config summary", async () => {
    server.use(
      http.get("/api/runs", () => HttpResponse.json([runningRun, completedRun])),
    );
    renderWithProviders(<Runs />);
    expect(await screen.findByText("#7")).toBeInTheDocument();
    expect(screen.getByText("#8")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getAllByText(/3 models · 4 strategies · 2 questions/).length).toBe(2);
  });

  it("shows an empty state", async () => {
    server.use(http.get("/api/runs", () => HttpResponse.json([])));
    renderWithProviders(<Runs />);
    expect(await screen.findByText(/No runs recorded yet/)).toBeInTheDocument();
  });
});
