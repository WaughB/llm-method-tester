import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getJson } from "../api/client";

interface LogRow {
  id: number;
  ts: string;
  level: string;
  component: string;
  message: string;
  trace_id: string | null;
  data: Record<string, unknown> | null;
}

interface TraceStage {
  name: string;
  ms: number;
  candidates: number;
  tokens: number;
  detail?: Record<string, unknown>;
}

interface Trace {
  trace_id: string;
  question: string;
  model: string;
  pipeline: string;
  stages: TraceStage[];
  total_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  llm_calls: number;
  answer: string;
}

const LEVEL_STYLES: Record<string, string> = {
  ERROR: "text-critical",
  WARNING: "text-warning",
  INFO: "text-sub",
  DEBUG: "text-muted",
};

export default function Logs() {
  const [params] = useSearchParams();
  const [level, setLevel] = useState("");
  const [component, setComponent] = useState("");
  const [text, setText] = useState("");
  const [traceId, setTraceId] = useState(params.get("trace") ?? "");

  const logs = useQuery({
    queryKey: ["logs", level, component, text, traceId],
    queryFn: () => {
      const search = new URLSearchParams();
      if (level) search.set("level", level);
      if (component) search.set("component", component);
      if (text) search.set("q", text);
      if (traceId) search.set("trace_id", traceId);
      return getJson<{ logs: LogRow[]; total: number }>(`/api/logs?${search}`);
    },
    refetchInterval: 10000,
  });

  const trace = useQuery({
    queryKey: ["trace", traceId],
    queryFn: () => getJson<Trace>(`/api/traces/${traceId}`),
    enabled: traceId.length > 8,
    retry: false,
  });

  return (
    <div className="max-w-5xl">
      <header className="mb-6">
        <div className="section-tag mb-1">observability</div>
        <h2 className="text-xl font-semibold">Logs</h2>
      </header>

      <div className="flex flex-wrap gap-2 mb-5">
        <select
          aria-label="level filter"
          value={level}
          onChange={(event) => setLevel(event.target.value)}
          className="bg-surface border border-hairline rounded-sm px-2 py-1.5 text-sm outline-none"
        >
          <option value="">all levels</option>
          {["INFO", "WARNING", "ERROR"].map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
        <input
          aria-label="component filter"
          value={component}
          onChange={(event) => setComponent(event.target.value)}
          placeholder="component…"
          className="bg-surface border border-hairline rounded-sm px-3 py-1.5 text-sm w-44 outline-none focus:border-s1"
        />
        <input
          aria-label="text filter"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="message contains…"
          className="bg-surface border border-hairline rounded-sm px-3 py-1.5 text-sm w-52 outline-none focus:border-s1"
        />
        <input
          aria-label="trace filter"
          value={traceId}
          onChange={(event) => setTraceId(event.target.value)}
          placeholder="trace id…"
          className="bg-surface border border-hairline rounded-sm px-3 py-1.5 font-mono text-xs w-72 outline-none focus:border-s1"
        />
        <span className="text-[11px] text-muted self-center">
          {logs.data ? `${logs.data.total} rows` : "…"}
        </span>
      </div>

      {trace.data && <TraceWaterfall trace={trace.data} />}

      <div className="panel overflow-x-auto">
        <table className="w-full text-xs">
          <tbody>
            {logs.data?.logs.map((row) => (
              <tr key={row.id} className="border-b border-hairline/40 align-top">
                <td className="px-3 py-1.5 font-mono text-[10px] text-muted whitespace-nowrap">
                  {row.ts.slice(11, 19)}
                </td>
                <td
                  className={`px-3 py-1.5 font-mono text-[10px] ${LEVEL_STYLES[row.level] ?? ""}`}
                >
                  {row.level}
                </td>
                <td className="px-3 py-1.5 font-mono text-[10px] text-muted">{row.component}</td>
                <td className="px-3 py-1.5">
                  {row.message}
                  {row.data && (
                    <span className="font-mono text-[10px] text-muted ml-2">
                      {JSON.stringify(row.data)}
                    </span>
                  )}
                </td>
                <td className="px-3 py-1.5">
                  {row.trace_id && (
                    <button
                      onClick={() => setTraceId(row.trace_id!)}
                      className="font-mono text-[10px] text-s1 hover:underline"
                    >
                      {row.trace_id.slice(0, 8)}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {logs.data?.logs.length === 0 && (
              <tr>
                <td className="px-4 py-8 text-center text-sub">No log rows match.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TraceWaterfall({ trace }: { trace: Trace }) {
  const max = Math.max(...trace.stages.map((s) => s.ms), 1);
  return (
    <section className="panel px-5 py-4 mb-5">
      <header className="flex items-baseline justify-between mb-3">
        <div className="section-tag">trace waterfall</div>
        <span className="font-mono text-[10px] text-muted">
          {trace.pipeline} · {trace.model} · {Math.round(trace.total_ms)}ms ·{" "}
          {trace.prompt_tokens + trace.completion_tokens} tok · {trace.llm_calls} calls
        </span>
      </header>
      <p className="text-sm text-sub mb-3">{trace.question}</p>
      <div className="space-y-1.5">
        {trace.stages.map((stage, index) => (
          <div key={index} className="flex items-center gap-3">
            <span className="font-mono text-[10px] text-sub w-24 shrink-0">{stage.name}</span>
            <div className="flex-1 h-3 bg-raised rounded-sm overflow-hidden">
              <div
                className="h-full bg-s1/70 rounded-sm"
                style={{ width: `${Math.max(2, (stage.ms / max) * 100)}%` }}
              />
            </div>
            <span className="font-mono text-[10px] text-muted w-40 shrink-0 text-right">
              {Math.round(stage.ms)}ms
              {stage.candidates ? ` · ${stage.candidates} cand` : ""}
              {stage.tokens ? ` · ${stage.tokens} tok` : ""}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
