import type { SummaryRow } from "../api/types";
import { modelsIn, strategiesIn } from "../lib/aggregate";
import { fmtScore, modelShort, strategyLabel } from "../lib/format";
import { heatColor } from "../theme/palette";

/** Model x strategy grid of judge scores; color is a sequential ramp, and the
 * score itself is printed in every cell so color never carries meaning alone. */
export function ScoreHeatmap({ rows, delay = 0 }: { rows: SummaryRow[]; delay?: number }) {
  const models = modelsIn(rows);
  const strategies = strategiesIn(rows);
  const byKey = new Map(rows.map((r) => [`${r.model}|${r.strategy}`, r]));
  return (
    <section className="panel px-5 py-4 rise" style={{ animationDelay: `${delay}ms` }}>
      <header className="flex items-baseline justify-between mb-4">
        <div className="section-tag">matrix</div>
        <h3 className="text-sm text-sub">Judge score, model × strategy</h3>
      </header>
      <div
        className="grid gap-[2px]"
        style={{ gridTemplateColumns: `120px repeat(${strategies.length}, 1fr)` }}
      >
        <div />
        {strategies.map((strategy) => (
          <div key={strategy} className="text-[11px] text-muted text-center pb-1">
            {strategyLabel(strategy)}
          </div>
        ))}
        {models.map((model) => (
          <HeatRow key={model} model={model} strategies={strategies} byKey={byKey} />
        ))}
      </div>
    </section>
  );
}

function HeatRow({
  model,
  strategies,
  byKey,
}: {
  model: string;
  strategies: string[];
  byKey: Map<string, SummaryRow>;
}) {
  return (
    <>
      <div className="text-[11px] font-mono text-sub self-center pr-3 text-right">
        {modelShort(model)}
      </div>
      {strategies.map((strategy) => {
        const row = byKey.get(`${model}|${strategy}`);
        const score = row?.avg_judge_score ?? null;
        return (
          <div
            key={strategy}
            title={`${model} / ${strategy}: ${fmtScore(score)}`}
            className="h-12 flex items-center justify-center rounded-[2px]"
            style={{ background: heatColor(score) }}
          >
            <span className="font-mono text-sm font-medium text-white/95">{fmtScore(score)}</span>
          </div>
        );
      })}
    </>
  );
}
