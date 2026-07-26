import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SummaryRow } from "../api/types";
import { groupByStrategy, modelsIn } from "../lib/aggregate";
import { modelShort, strategyLabel } from "../lib/format";
import { CHART_INK, modelColor } from "../theme/palette";

interface GroupedBarsProps {
  tag: string;
  title: string;
  rows: SummaryRow[];
  metric: keyof SummaryRow;
  domain?: [number, number];
  format?: (value: number) => string;
  delay?: number;
}

export function GroupedBars({
  tag,
  title,
  rows,
  metric,
  domain,
  format = (v) => v.toFixed(2),
  delay = 0,
}: GroupedBarsProps) {
  const data = groupByStrategy(rows, metric).map((group) => ({
    ...group,
    strategy: strategyLabel(group.strategy as string),
  }));
  const models = modelsIn(rows);
  return (
    <section
      className="panel px-5 pt-4 pb-2 rise"
      style={{ animationDelay: `${delay}ms` }}
      aria-label={title}
    >
      <header className="flex items-baseline justify-between mb-3">
        <div className="section-tag">{tag}</div>
        <h3 className="text-sm text-sub">{title}</h3>
      </header>
      <ResponsiveContainer width="100%" height={230}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: -18, bottom: 0 }} barGap={2}>
          <CartesianGrid stroke={CHART_INK.grid} strokeWidth={1} vertical={false} />
          <XAxis
            dataKey="strategy"
            tick={{ fill: CHART_INK.muted, fontSize: 11 }}
            axisLine={{ stroke: CHART_INK.baseline }}
            tickLine={false}
          />
          <YAxis
            domain={domain ?? [0, "auto"]}
            tick={{ fill: CHART_INK.muted, fontSize: 11, fontFamily: "IBM Plex Mono" }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            contentStyle={{
              background: CHART_INK.surface,
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 2,
              fontSize: 12,
            }}
            labelStyle={{ color: CHART_INK.sub }}
            formatter={(value: number | string, name: string) => [
              typeof value === "number" ? format(value) : "—",
              modelShort(String(name)),
            ]}
          />
          <Legend
            formatter={(value: string) => (
              <span style={{ color: CHART_INK.sub, fontSize: 12 }}>{modelShort(value)}</span>
            )}
            iconType="square"
            iconSize={9}
          />
          {models.map((model) => (
            <Bar
              key={model}
              dataKey={model}
              fill={modelColor(model)}
              radius={[3, 3, 0, 0]}
              maxBarSize={26}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}
