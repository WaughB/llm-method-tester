import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { renderRoute } from "../test/render";
import { runningRun } from "../test/fixtures";
import { server } from "../test/server";
import RunDetail from "./RunDetail";

function renderDetail(runId = 7) {
  return renderRoute("/runs/:runId", <RunDetail />, `/runs/${runId}`);
}

describe("RunDetail", () => {
  it("renders the results table with metrics", async () => {
    renderDetail();
    expect(await screen.findByText("#7")).toBeInTheDocument();
    const cells = await screen.findAllByText("sh-01");
    expect(cells.length).toBeGreaterThan(0);
    expect(screen.getAllByText("Vector RAG").length).toBeGreaterThan(0);
  });

  it("drills into a question showing side-by-side answers and gold sources", async () => {
    const user = userEvent.setup();
    renderDetail();
    await screen.findByText("#7");
    await user.click((await screen.findAllByRole("button", { name: "sh-01" }))[0]);
    expect(
      await screen.findByText(/What TCP port does the Aurora Mesh control plane listen on\?/),
    ).toBeInTheDocument();
    expect(screen.getByText(/gold ·/)).toBeInTheDocument();
    // baseline answer shown side by side with the RAG answer
    expect(screen.getByText(/I do not know of a system called Aurora Mesh/)).toBeInTheDocument();
    // retrieved source chip is highlighted as gold
    expect(screen.getAllByTitle("gold source").length).toBeGreaterThan(0);
  });

  it("shows the progress bar while a run is active", async () => {
    server.use(http.get("/api/runs/8", () => HttpResponse.json(runningRun)));
    server.use(http.get("/api/runs/8/results", () => HttpResponse.json([])));
    renderDetail(8);
    expect(await screen.findByRole("progressbar")).toBeInTheDocument();
    expect(screen.getByText(/llama3\.1:8b \/ baseline \/ sh-03/)).toBeInTheDocument();
  });

  it("renders a not-found message for unknown runs", async () => {
    server.use(
      http.get("/api/runs/99", () => HttpResponse.json({ detail: "no" }, { status: 404 })),
    );
    renderDetail(99);
    expect(await screen.findByText(/Run not found/)).toBeInTheDocument();
  });
});
