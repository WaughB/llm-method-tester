import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import type { Citation, Message } from "../api/types";

export default function Chat() {
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [usePageindex, setUsePageindex] = useState(true);

  const conversations = useQuery({ queryKey: ["conversations"], queryFn: api.conversations });
  const active = useQuery({
    queryKey: ["conversation", activeId],
    queryFn: () => api.conversation(activeId!),
    enabled: activeId != null,
  });

  const create = useMutation({
    mutationFn: () => api.createConversation({}),
    onSuccess: (conversation) => {
      setActiveId(conversation.id);
      queryClient.invalidateQueries({ queryKey: ["conversations"] });
    },
  });

  const ask = useMutation({
    mutationFn: ({ id, q }: { id: string; q: string }) => api.ask(id, q, usePageindex),
    onSuccess: () => {
      setQuestion("");
      queryClient.invalidateQueries({ queryKey: ["conversation", activeId] });
    },
  });

  const submit = () => {
    if (!question.trim() || !activeId || ask.isPending) return;
    ask.mutate({ id: activeId, q: question.trim() });
  };

  return (
    <div className="flex gap-6 h-[calc(100vh-4rem)]">
      <aside className="w-60 shrink-0 flex flex-col">
        <button
          onClick={() => create.mutate()}
          className="font-mono text-sm border border-s1 text-s1 px-3 py-2 rounded-sm hover:bg-s1 hover:text-page transition-colors mb-3"
        >
          NEW CONVERSATION +
        </button>
        <div className="overflow-y-auto space-y-1">
          {conversations.data?.map((conversation) => (
            <button
              key={conversation.id}
              onClick={() => setActiveId(conversation.id)}
              className={`w-full text-left px-3 py-2 rounded-sm text-sm transition-colors ${
                conversation.id === activeId
                  ? "bg-raised text-ink border-l-2 border-s1"
                  : "text-sub hover:bg-raised/60"
              }`}
            >
              <div className="truncate">{conversation.title}</div>
              <div className="font-mono text-[10px] text-muted">{conversation.model}</div>
            </button>
          ))}
        </div>
      </aside>

      <section className="flex-1 min-w-0 flex flex-col">
        {activeId == null ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="section-tag mb-2">ask your documents</div>
              <p className="text-sub text-sm">Start a new conversation to query the library.</p>
            </div>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto space-y-4 pr-2">
              {active.data?.messages?.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {ask.isPending && (
                <div className="text-sm text-muted font-mono animate-pulse">
                  running pipeline…
                </div>
              )}
              {ask.isError && (
                <p role="alert" className="text-sm text-critical">
                  {(ask.error as Error).message}
                </p>
              )}
            </div>
            <div className="pt-4 border-t border-hairline mt-4">
              <div className="flex items-center gap-3 mb-2">
                <label className="flex items-center gap-2 text-[11px] text-sub cursor-pointer">
                  <input
                    type="checkbox"
                    checked={usePageindex}
                    onChange={(event) => setUsePageindex(event.target.checked)}
                    className="accent-[#3987e5]"
                  />
                  PageIndex precision stage
                </label>
              </div>
              <div className="flex gap-2">
                <textarea
                  aria-label="question"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !event.shiftKey) {
                      event.preventDefault();
                      submit();
                    }
                  }}
                  rows={2}
                  placeholder="Ask a question about your documents…"
                  className="flex-1 bg-surface border border-hairline rounded-sm px-3 py-2 text-sm resize-none focus:border-s1 outline-none"
                />
                <button
                  onClick={submit}
                  disabled={!question.trim() || ask.isPending}
                  className="font-mono text-sm border border-s1 text-s1 px-4 rounded-sm hover:bg-s1 hover:text-page transition-colors disabled:opacity-40"
                >
                  ASK →
                </button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function MessageBubble({ message }: { message: Message }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] bg-raised border border-hairline rounded-sm px-4 py-2.5 text-sm">
          {message.content}
        </div>
      </div>
    );
  }
  return (
    <div className="max-w-[85%]">
      <div className="panel px-4 py-3 text-sm whitespace-pre-wrap">{message.content}</div>
      {message.citations && message.citations.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2">
          {message.citations.map((citation, index) => (
            <CitationChip key={index} citation={citation} />
          ))}
        </div>
      )}
      {message.trace_id && (
        <a
          href={`/logs?trace=${message.trace_id}`}
          className="inline-block mt-1.5 font-mono text-[10px] text-muted hover:text-s1"
        >
          trace {message.trace_id.slice(0, 8)} →
        </a>
      )}
    </div>
  );
}

function CitationChip({ citation }: { citation: Citation }) {
  const [open, setOpen] = useState(false);
  return (
    <button
      onClick={() => setOpen(!open)}
      className="text-left font-mono text-[10px] border border-hairline text-sub px-2 py-1 rounded-sm hover:border-s1 transition-colors"
      title={citation.snippet}
    >
      § {citation.heading || citation.doc_id.slice(0, 8)}
      {open && (
        <span className="block mt-1 text-muted normal-case font-sans text-[11px] max-w-xs">
          {citation.snippet}…
        </span>
      )}
    </button>
  );
}
