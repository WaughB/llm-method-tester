import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { renderWithProviders } from "../test/render";
import { server } from "../test/server";
import NewRun from "./NewRun";

describe("NewRun", () => {
  it("lists models and strategies from /api/meta", async () => {
    renderWithProviders(<NewRun />);
    expect(await screen.findByText("gpt-oss:20b")).toBeInTheDocument();
    expect(screen.getByText("PageIndex (reimpl)")).toBeInTheDocument();
    expect(screen.getByText("Baseline")).toBeInTheDocument();
  });

  it("computes the cell count from selections", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NewRun />);
    // all defaults: 3 models x 4 strategies x 30 questions
    expect(await screen.findByText("360")).toBeInTheDocument();
    await user.click(screen.getByText("gpt-oss:20b"));
    // 1 model x 4 strategies x 30 questions
    expect(await screen.findByText("120")).toBeInTheDocument();
  });

  it("launches a run", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NewRun />);
    await screen.findByText("gpt-oss:20b");
    await user.click(screen.getByRole("button", { name: /LAUNCH/ }));
    // navigation target isn't mounted here; success = no error surfaced
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("surfaces a 409 as an error message", async () => {
    server.use(
      http.post("/api/runs", () =>
        HttpResponse.json({ detail: "a run is already in progress" }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    renderWithProviders(<NewRun />);
    await screen.findByText("gpt-oss:20b");
    await user.click(screen.getByRole("button", { name: /LAUNCH/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/already in progress/);
  });
});
