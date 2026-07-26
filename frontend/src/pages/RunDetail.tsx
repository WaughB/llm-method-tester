import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Question, ResultRow } from "../api/types";
import { RunProgressBar } from "../components/RunProgressBar";
import {
  CATEGORY_LABELS,
  fmtLatency,
  fmtPct,
  fmtScore,
  modelShort,
  strategyLabel,
} from "../lib/format";
import { modelColor } from "../theme/palette";

export default function RunDetail() {
  const { runId } = useParams();
  const id = Number(runId);
  const [questionFilter, setQuestionFilter] = useState<string | null>(null);

  const run = useQuery({
    queryKey: ["run", id],
    queryFn: () => api.run(id),
    refetchInterval: (query) => (query.state.data?.status === "running" ? 2000 : false),
  });
  const results = useQuery({
    queryKey: ["results", id, run.data?.status],
    queryFn: () => api.results(id),
    enabled: run.data != null,
  });
  const questions = useQuery({ queryKey: ["questions"], queryFn: api.questions });

  const questionById = useMemo(
    () => new Map((questions.data ?? []).map((q) => [q.id, q])),
    [questions.data],
  );
  const rows = useMemo(() => results.data ?? [], [results.data]);
  const questionIds = useMemo(() => [...new Set(rows.map((r) => r.question_id))], [rows]);

  if (run.isLoading) return <p className="text-sub">loading run…</p>;
  if (!run.data) return <p className="text-critical">Run not found.</p>;

  return (
    <div>
      <header className="mb-6">
        <div className="section-tag mb-1">run detail</div>
        <div className="flex items-baseline gap-4">
          <h2 className="text-xl font-semibold font-mono">#{id}</h2>
          <span className="font-mono text-xs text-muted">
            {run.data.status} · started {new Date(run.data.started_at).toLocaleString()}
          </span>
          <Link to="/runs" className="text-xs text-s1 hover:underline ml-auto font-mono">
            ← all runs
          </Link>
        </div>
      </header>

      {run.data.status === "running" && (
        <div className="panel px-5 py-4 mb-6">
          <RunProgressBar progress={run.data.progress} />
        </div>
      )}
      {run.data.status === "failed" && (
        <div className="panel border-critical/40 px-5 py-4 mb-6 text-sm text-critical">
          Run failed: {run.data.error}
        </div>
      )}

      {questionIds.length > 0 && (
        <>
          <div className="flex flex-wrap gap-1.5 mb-5">
            <FilterChip
              label="all questions"
              active={questionFilter === null}
              onClick={() => setQuestionFilter(null)}
            />
            {questionIds.map((qid) => (
              <FilterChip
                key={qid}
                label={qid}
                active={questionFilter === qid}
                onClick={() => setQuestionFilter(qid)}
              />
            ))}
          </div>

          {questionFilter === null ? (
            <ResultsTable rows={rows} onPick={setQuestionFilter} />
          ) : (
            <QuestionDrilldown
              rows={rows.filter((r) => r.question_id === questionFilter)}
              question={questionById.get(questionFilter)}
            />
          )}
        </>
      )}
    </div>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`font-mono text-[11px] px-2 py-1 rounded-sm border transition-colors ${
        active ? "border-s1 text-ink bg-s1/15" : "border-hairline text-muted hover:text-sub"
      }`}
    >
      {label}
    </button>
  );
}

function ResultsTable({
  rows,
  onPick,
}: {
  rows: ResultRow[];
  onPick: (questionId: string) => void;
}) {
  return (
    <div className="panel overflow-x-auto rise">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left border-b border-hairline">
            {["question", "model", "strategy", "judge", "recall", "hit rate", "latency", "calls"].map(
              (h) => (
                <th key={h} className="section-tag font-normal px-4 py-3">
                  {h}
                </th>
              ),
            )}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={`${row.model}|${row.strategy}|${row.question_id}`}
              className="border-b border-hairline/50 hover:bg-raised/60 cursor-pointer"
              onClick={() => onPick(row.question_id)}
            >
              <td className="px-4 py-2 font-mono text-xs text-sub">{row.question_id}</td>
              <td className="px-4 py-2">
                <span className="inline-flex items-center gap-1.5">
                  <span
                    className="w-2 h-2 rounded-full inline-block"
                    style={{ background: modelColor(row.model) }}
                  />
                  <span className="font-mono text-xs">{modelShort(row.model)}</span>
                </span>
              </td>
              <td className="px-4 py-2 text-sub">{strategyLabel(row.strategy)}</td>
              <td className="px-4 py-2 font-mono">
                {row.error ? (
                  <span className="text-critical text-xs">error</span>
                ) : (
                  fmtScore(row.judge_score)
                )}
              </td>
              <td className="px-4 py-2 font-mono">{fmtPct(row.keyword_recall)}</td>
              <td className="px-4 py-2 font-mono">{fmtPct(row.retrieval_hit_rate)}</td>
              <td className="px-4 py-2 font-mono">{fmtLatency(row.latency_ms)}</td>
              <td className="px-4 py-2 font-mono">{row.llm_calls}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function QuestionDrilldown({
  rows,
  question,
}: {
  rows: ResultRow[];
  question: Question | undefined;
}) {
  return (
    <div>
      {question && (
        <div className="panel px-5 py-4 mb-4 rise">
          <div className="flex items-baseline gap-3 mb-2">
            <span className="section-tag">{CATEGORY_LABELS[question.category]}</span>
            <span className="font-mono text-[10px] text-muted">{question.id}</span>
          </div>
          <p className="text-base mb-3">{question.question}</p>
          <div className="text-xs text-sub">
            <span className="text-good font-mono">gold ·</span> {question.gold_answer}
          </div>
        </div>
      )}
      <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
        {rows.map((row, i) => (
          <AnswerCard key={`${row.model}|${row.strategy}`} row={row} question={question} index={i} />
        ))}
      </div>
    </div>
  );
}

function AnswerCard({
  row,
  question,
  index,
}: {
  row: ResultRow;
  question: Question | undefined;
  index: number;
}) {
  const goldSources = new Set([...(question?.source_docs ?? []), ...(question?.source_notes ?? [])]);
  return (
    <article className="panel px-4 py-3 rise" style={{ animationDelay: `${index * 50}ms` }}>
      <header className="flex items-center justify-between mb-2">
        <span className="inline-flex items-center gap-1.5">
          <span
            className="w-2 h-2 rounded-full inline-block"
            style={{ background: modelColor(row.model) }}
          />
          <span className="font-mono text-xs">{modelShort(row.model)}</span>
          <span className="text-xs text-muted">/ {strategyLabel(row.strategy)}</span>
        </span>
        <span className="font-mono text-sm">
          {row.error ? <span className="text-critical text-xs">error</span> : fmtScore(row.judge_score)}
        </span>
      </header>
      {row.error ? (
        <p className="text-xs text-critical/80 font-mono">{row.error}</p>
      ) : (
        <>
          <p className="text-xs text-sub leading-relaxed mb-3 max-h-36 overflow-y-auto whitespace-pre-wrap">
            {row.answer}
          </p>
          {row.retrieved_ids.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              {row.retrieved_ids.map((sourceId) => (
                <span
                  key={sourceId}
                  className={`font-mono text-[10px] px-1.5 py-0.5 rounded-sm border ${
                    goldSources.has(sourceId)
                      ? "border-good/50 text-good"
                      : "border-hairline text-muted"
                  }`}
                  title={goldSources.has(sourceId) ? "gold source" : "not a gold source"}
                >
                  {sourceId.split("/").pop()}
                </span>
              ))}
            </div>
          )}
          {row.judge_reasoning && (
            <p className="text-[11px] text-muted italic border-t border-hairline pt-2">
              judge: {row.judge_reasoning}
            </p>
          )}
        </>
      )}
    </article>
  );
}
