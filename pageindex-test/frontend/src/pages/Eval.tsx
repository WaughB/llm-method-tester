import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { getJson, sendJson } from "../api/client";

interface EvalSet {
  id: string;
  name: string;
  question_count?: number;
  approved_count?: number;
}

interface EvalQuestion {
  id: string;
  question: string;
  expected_keywords: string[][];
  gold_doc_ids: string[];
  source: string;
  approved: boolean;
}

interface EvalRun {
  id: string;
  model: string;
  pipeline: "staged" | "hybrid_only";
  status: string;
  summary: {
    count?: number;
    avg_keyword_recall?: number | null;
    avg_retrieval_hit?: number | null;
    avg_judge_score?: number | null;
  } | null;
}

interface SetDetail extends EvalSet {
  questions: EvalQuestion[];
  runs: EvalRun[];
}

const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);
const score = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(2));

export default function Eval() {
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [name, setName] = useState("");

  const sets = useQuery({
    queryKey: ["eval-sets"],
    queryFn: () => getJson<{ sets: EvalSet[] }>("/api/eval-sets").then((r) => r.sets),
  });
  const detail = useQuery({
    queryKey: ["eval-set", activeId],
    queryFn: () => getJson<SetDetail>(`/api/eval-sets/${activeId}`),
    enabled: activeId != null,
    refetchInterval: (query) =>
      query.state.data?.runs.some((r) => r.status === "queued" || r.status === "running")
        ? 3000
        : false,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["eval-sets"] });
    queryClient.invalidateQueries({ queryKey: ["eval-set", activeId] });
  };
  const createSet = useMutation({
    mutationFn: () => sendJson<EvalSet>("POST", "/api/eval-sets", { name }),
    onSuccess: (created) => {
      setName("");
      setActiveId(created.id);
      invalidate();
    },
  });
  const generate = useMutation({
    mutationFn: () => sendJson("POST", `/api/eval-sets/${activeId}/generate`, {}),
    onSuccess: invalidate,
  });
  const launch = useMutation({
    mutationFn: () => sendJson("POST", `/api/eval-sets/${activeId}/runs`, {}),
    onSuccess: invalidate,
  });
  const approve = useMutation({
    mutationFn: ({ id, approved }: { id: string; approved: boolean }) =>
      sendJson("PUT", `/api/eval-questions/${id}/approved`, { approved }),
    onSuccess: invalidate,
  });

  return (
    <div className="max-w-5xl">
      <header className="mb-6">
        <div className="section-tag mb-1">measurement</div>
        <h2 className="text-xl font-semibold">Eval</h2>
      </header>

      <div className="flex gap-2 mb-6">
        <input
          aria-label="new set name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="New gold set name…"
          className="bg-surface border border-hairline rounded-sm px-3 py-1.5 text-sm w-64 focus:border-s1 outline-none"
        />
        <button
          onClick={() => name.trim() && createSet.mutate()}
          disabled={!name.trim()}
          className="font-mono text-xs border border-s1 text-s1 px-3 rounded-sm hover:bg-s1 hover:text-page transition-colors disabled:opacity-40"
        >
          CREATE
        </button>
        {sets.data?.map((set) => (
          <button
            key={set.id}
            onClick={() => setActiveId(set.id)}
            className={`text-sm px-3 py-1.5 rounded-sm border transition-colors ${
              set.id === activeId
                ? "border-s1 bg-s1/15 text-ink"
                : "border-hairline text-sub hover:border-muted"
            }`}
          >
            {set.name}
            <span className="font-mono text-[10px] text-muted ml-2">
              {set.approved_count}/{set.question_count}
            </span>
          </button>
        ))}
      </div>

      {detail.data && (
        <>
          <section className="mb-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="section-tag">questions</div>
              <button
                onClick={() => generate.mutate()}
                className="font-mono text-[11px] border border-hairline text-sub px-2 py-1 rounded-sm hover:border-s1 hover:text-s1"
              >
                GENERATE FROM DOCUMENTS
              </button>
              <span className="text-[11px] text-muted">
                generated questions need approval before they count
              </span>
            </div>
            <div className="panel overflow-x-auto">
              <table className="w-full text-sm">
                <tbody>
                  {detail.data.questions.map((question) => (
                    <tr key={question.id} className="border-b border-hairline/50">
                      <td className="px-4 py-2">{question.question}</td>
                      <td className="px-4 py-2 font-mono text-[10px] text-muted">
                        {question.expected_keywords.map((g) => g[0]).join(" · ")}
                      </td>
                      <td className="px-4 py-2 font-mono text-[10px] text-muted">
                        {question.source}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <button
                          onClick={() =>
                            approve.mutate({ id: question.id, approved: !question.approved })
                          }
                          className={`font-mono text-[10px] uppercase border px-2 py-0.5 rounded-sm ${
                            question.approved
                              ? "text-good border-good/40"
                              : "text-muted border-hairline"
                          }`}
                        >
                          {question.approved ? "approved" : "approve?"}
                        </button>
                      </td>
                    </tr>
                  ))}
                  {detail.data.questions.length === 0 && (
                    <tr>
                      <td className="px-4 py-6 text-center text-sub text-sm">
                        No questions yet — generate some or add them via the API.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <div className="flex items-center gap-3 mb-3">
              <div className="section-tag">runs</div>
              <button
                onClick={() => launch.mutate()}
                className="font-mono text-[11px] border border-s1 text-s1 px-2 py-1 rounded-sm hover:bg-s1 hover:text-page"
              >
                RUN STAGED VS HYBRID →
              </button>
            </div>
            <Comparison runs={detail.data.runs} />
          </section>
        </>
      )}
    </div>
  );
}

function Comparison({ runs }: { runs: EvalRun[] }) {
  const staged = runs.filter((r) => r.pipeline === "staged" && r.status === "done").at(-1);
  const hybrid = runs.filter((r) => r.pipeline === "hybrid_only" && r.status === "done").at(-1);
  const running = runs.filter((r) => r.status === "queued" || r.status === "running");
  return (
    <div>
      {running.length > 0 && (
        <p className="text-xs text-warning font-mono animate-pulse mb-3">
          {running.length} run(s) in progress…
        </p>
      )}
      <div className="grid grid-cols-3 gap-3">
        <Tile
          tag="judge score"
          staged={score(staged?.summary?.avg_judge_score)}
          hybrid={score(hybrid?.summary?.avg_judge_score)}
        />
        <Tile
          tag="keyword recall"
          staged={pct(staged?.summary?.avg_keyword_recall)}
          hybrid={pct(hybrid?.summary?.avg_keyword_recall)}
        />
        <Tile
          tag="retrieval hit"
          staged={pct(staged?.summary?.avg_retrieval_hit)}
          hybrid={pct(hybrid?.summary?.avg_retrieval_hit)}
        />
      </div>
    </div>
  );
}

function Tile({ tag, staged, hybrid }: { tag: string; staged: string; hybrid: string }) {
  return (
    <div className="panel px-4 py-3">
      <div className="section-tag mb-2">{tag}</div>
      <div className="flex items-baseline gap-4">
        <div>
          <div className="font-mono text-xl">{staged}</div>
          <div className="text-[10px] text-muted">staged</div>
        </div>
        <div>
          <div className="font-mono text-xl text-sub">{hybrid}</div>
          <div className="text-[10px] text-muted">hybrid-only</div>
        </div>
      </div>
    </div>
  );
}
