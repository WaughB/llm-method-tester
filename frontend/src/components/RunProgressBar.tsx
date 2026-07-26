import type { RunProgress } from "../api/types";

export function RunProgressBar({ progress }: { progress: RunProgress | null | undefined }) {
  if (!progress) {
    return (
      <div className="text-xs text-muted font-mono animate-pulse">preparing run…</div>
    );
  }
  const pct = progress.total > 0 ? Math.round((progress.done / progress.total) * 100) : 0;
  return (
    <div>
      <div className="flex justify-between text-xs font-mono text-sub mb-1.5">
        <span>{progress.current}</span>
        <span>
          {progress.done}/{progress.total} · {pct}%
        </span>
      </div>
      <div
        className="h-1.5 bg-raised rounded-full overflow-hidden"
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full bg-s1 rounded-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
