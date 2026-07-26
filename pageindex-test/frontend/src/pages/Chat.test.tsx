import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import type { Conversation } from "../api/types";
import { renderWithProviders } from "../test/render";
import { server } from "../test/server";
import Chat from "./Chat";

const conversation: Conversation = {
  id: "conv-1",
  title: "ports",
  model: "llama3.1:8b",
  use_pageindex_stage: true,
  created_at: "2026-07-26T10:00:00Z",
};

function useChatHandlers(messages: unknown[] = []) {
  server.use(
    http.get("/api/conversations", () => HttpResponse.json({ conversations: [conversation] })),
    http.get("/api/conversations/conv-1", () =>
      HttpResponse.json({ ...conversation, messages }),
    ),
  );
}

describe("Chat", () => {
  it("shows the empty state until a conversation is selected", async () => {
    useChatHandlers();
    renderWithProviders(<Chat />);
    expect(await screen.findByText(/Start a new conversation/)).toBeInTheDocument();
    expect(await screen.findByText("ports")).toBeInTheDocument();
  });

  it("renders messages with citations and trace link", async () => {
    useChatHandlers([
      {
        id: 1,
        role: "user",
        content: "Which port?",
        citations: null,
        trace_id: null,
        created_at: "",
      },
      {
        id: 2,
        role: "assistant",
        content: "Port 7433.",
        citations: [
          { doc_id: "d1", chunk_id: "d1#0", heading: "Network ports", snippet: "listens on 7433" },
        ],
        trace_id: "trace-abcdef12",
        created_at: "",
      },
    ]);
    const user = userEvent.setup();
    renderWithProviders(<Chat />);
    await user.click(await screen.findByText("ports"));
    expect(await screen.findByText("Port 7433.")).toBeInTheDocument();
    expect(screen.getByText(/§ Network ports/)).toBeInTheDocument();
    expect(screen.getByText(/trace trace-ab/)).toBeInTheDocument();
  });

  it("sends a question with the pageindex toggle state", async () => {
    useChatHandlers();
    let asked: unknown = null;
    server.use(
      http.post("/api/conversations/conv-1/messages", async ({ request }) => {
        asked = await request.json();
        return HttpResponse.json({
          answer: "a",
          citations: [],
          trace_id: "t",
          pipeline: "staged",
          total_ms: 5,
          stages: [],
        });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<Chat />);
    await user.click(await screen.findByText("ports"));
    await user.type(await screen.findByLabelText("question"), "Which port?");
    await user.click(screen.getByRole("button", { name: /ASK/ }));
    expect(asked).toEqual({ question: "Which port?", use_pageindex_stage: true });
  });

  it("toggle off sends use_pageindex_stage false", async () => {
    useChatHandlers();
    let asked: Record<string, unknown> | null = null;
    server.use(
      http.post("/api/conversations/conv-1/messages", async ({ request }) => {
        asked = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({
          answer: "a",
          citations: [],
          trace_id: "t",
          pipeline: "hybrid_only",
          total_ms: 5,
          stages: [],
        });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<Chat />);
    await user.click(await screen.findByText("ports"));
    await user.click(screen.getByRole("checkbox"));
    await user.type(await screen.findByLabelText("question"), "q");
    await user.click(screen.getByRole("button", { name: /ASK/ }));
    expect((asked as Record<string, unknown> | null)?.use_pageindex_stage).toBe(false);
  });
});
