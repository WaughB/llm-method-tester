import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import type { StorageLocation } from "../api/types";
import { renderWithProviders } from "../test/render";
import { server } from "../test/server";
import Settings from "./Settings";

const locations: StorageLocation[] = [
  {
    location_id: "aaa111",
    host_label: "C:\\Users\\brett\\Desktop",
    available: true,
    free_bytes: 200 * 1024 ** 3,
    total_bytes: 1000 * 1024 ** 3,
    active: true,
  },
  {
    location_id: "bbb222",
    host_label: "E:\\archive",
    available: false,
    free_bytes: null,
    total_bytes: null,
    active: false,
  },
];

function useHandlers(locs: StorageLocation[] = locations) {
  server.use(
    http.get("/api/locations", () => HttpResponse.json({ locations: locs })),
    http.get("/api/settings", () =>
      HttpResponse.json({
        default_model: "llama3.1:8b",
        hybrid_top_n: 8,
        tree_stage_docs: 4,
        use_pageindex_stage: true,
      }),
    ),
  );
}

describe("Settings", () => {
  it("shows location cards with free space and active badge", async () => {
    useHandlers();
    renderWithProviders(<Settings />);
    expect(await screen.findByText("C:\\Users\\brett\\Desktop")).toBeInTheDocument();
    expect(screen.getByText("200 GB free of 1.0 TB")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("marks unavailable locations and disables activation", async () => {
    useHandlers();
    renderWithProviders(<Settings />);
    expect(await screen.findByText(/unavailable — is the drive mounted/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ACTIVATE" })).toBeDisabled();
  });

  it("activates an available inactive location", async () => {
    const swapped = [
      { ...locations[0], active: false },
      { ...locations[1], available: true, active: false, free_bytes: 1, total_bytes: 2 },
    ];
    useHandlers(swapped);
    let activated: string | null = null;
    server.use(
      http.put("/api/locations/active", async ({ request }) => {
        const body = (await request.json()) as { location_id: string };
        activated = body.location_id;
        return HttpResponse.json({});
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<Settings />);
    const buttons = await screen.findAllByRole("button", { name: "ACTIVATE" });
    await user.click(buttons[0]);
    expect(activated).toBe("aaa111");
  });

  it("saves the default model on blur", async () => {
    useHandlers();
    let saved: unknown = null;
    server.use(
      http.put("/api/settings", async ({ request }) => {
        saved = await request.json();
        return HttpResponse.json({
          default_model: "gpt-oss:20b",
          hybrid_top_n: 8,
          tree_stage_docs: 4,
          use_pageindex_stage: true,
        });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<Settings />);
    const input = await screen.findByLabelText("default model");
    await user.clear(input);
    await user.type(input, "gpt-oss:20b");
    await user.tab();
    expect(saved).toEqual({ default_model: "gpt-oss:20b" });
  });
});
