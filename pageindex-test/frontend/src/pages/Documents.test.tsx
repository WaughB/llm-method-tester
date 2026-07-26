import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import type { DocumentRow } from "../api/types";
import { renderWithProviders } from "../test/render";
import { server } from "../test/server";
import Documents from "./Documents";

const docs: DocumentRow[] = [
  {
    id: "d1",
    filename: "report.pdf",
    format: "pdf",
    status: "ready",
    error: null,
    title: "Annual Report",
    pages: 12,
    chunk_count: 34,
    created_at: "2026-07-26T10:00:00Z",
  },
  {
    id: "d2",
    filename: "scan.pdf",
    format: "pdf",
    status: "unsupported",
    error: "PDF appears to be scanned (almost no extractable text). OCR is not supported.",
    title: null,
    pages: null,
    chunk_count: null,
    created_at: "2026-07-26T10:01:00Z",
  },
];

function useDocs(rows: DocumentRow[] = docs) {
  server.use(http.get("/api/documents", () => HttpResponse.json({ documents: rows })));
}

describe("Documents", () => {
  it("lists documents with status badges and chunk counts", async () => {
    useDocs();
    renderWithProviders(<Documents />);
    expect(await screen.findByText("Annual Report")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
    expect(screen.getByText("34")).toBeInTheDocument();
  });

  it("surfaces the unsupported reason for scanned PDFs", async () => {
    useDocs();
    renderWithProviders(<Documents />);
    expect(await screen.findByText(/appears to be scanned/)).toBeInTheDocument();
    expect(screen.getByText("unsupported")).toBeInTheDocument();
  });

  it("shows the empty state", async () => {
    useDocs([]);
    renderWithProviders(<Documents />);
    expect(await screen.findByText(/No documents yet/)).toBeInTheDocument();
  });

  it("submits a bulk import path", async () => {
    useDocs([]);
    let imported: unknown = null;
    server.use(
      http.post("/api/documents/import", async ({ request }) => {
        imported = await request.json();
        return HttpResponse.json({ queued: [] }, { status: 202 });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<Documents />);
    await user.type(await screen.findByLabelText("import path"), "archive/2024");
    await user.click(screen.getByRole("button", { name: "IMPORT" }));
    expect(imported).toEqual({ path: "archive/2024" });
  });

  it("deletes a document", async () => {
    useDocs();
    let deleted: string | null = null;
    server.use(
      http.delete("/api/documents/:id", ({ params }) => {
        deleted = String(params.id);
        return HttpResponse.json({ deleted: params.id });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<Documents />);
    await user.click(await screen.findByLabelText("delete report.pdf"));
    expect(deleted).toBe("d1");
  });
});
