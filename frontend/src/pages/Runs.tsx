import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";

const STATUS_STYLES: Record<string, string> = {
  completed: "text-good border-good/40",
  running: "text-warning border-warning/40",
  failed: "text-critical border-critical/40",
};

export default function Runs() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: api.runs, refetchInterval: 5000 });
  return (
    <div className="max-w-3xl">
      <header className="mb-6">
        <div className="section-tag mb-1">history</div>
        <h2 className="text-xl font-semibold">Runs</h2>
      </header>
      {runs.isLoading && <p className="text-sub">loading…</p>}
      {runs.data?.length === 0 && <p className="text-sub">No runs recorded yet.</p>}
      <ul className="space-y-2">
        {runs.data?.map((run, i) => (
          <li key={run.id} className="rise" style={{ animationDelay: `${i * 40}ms` }}>
            <Link
              to={`/runs/${run.id}`}
              className="panel px-5 py-3 flex items-center justify-between hover:border-muted transition-colors"
            >
              <div className="flex items-center gap-4">
                <span className="font-mono text-lg text-ink">#{run.id}</span>
                <div className="text-xs text-sub">
                  <div>{new Date(run.started_at).toLocaleString()}</div>
                  <div className="font-mono text-[10px] text-muted">
                    {run.config.models?.length ?? "?"} models ·{" "}
                    {run.config.strategies?.length ?? "?"} strategies ·{" "}
                    {run.config.question_ids?.length ?? "?"} questions
                  </div>
                </div>
              </div>
              <span
                className={`font-mono text-[10px] uppercase tracking-widest border px-2 py-1 rounded-sm ${
                  STATUS_STYLES[run.status] ?? "text-sub border-hairline"
                }`}
              >
                {run.status}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
