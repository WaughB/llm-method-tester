import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { GroupedBars } from "../components/GroupedBars";
import { ScoreHeatmap } from "../components/ScoreHeatmap";
import { StatTile } from "../components/StatTile";
import { computeHeadline } from "../lib/aggregate";
import { fmtLatency, fmtScore, strategyLabel } from "../lib/format";

export default function Dashboard() {
  const runsQuery = useQuery({ queryKey: ["runs"], queryFn: api.runs });
  const latest = runsQuery.data?.find((run) => run.status === "completed");
  const summaryQuery = useQuery({
    queryKey: ["summary", latest?.id],
    queryFn: () => api.summary(latest!.id),
    enabled: latest != null,
  });
  const multiHopQuery = useQuery({
    queryKey: ["summary", latest?.id, "multi_hop"],
    queryFn: () => api.summary(latest!.id, "multi_hop"),
    enabled: latest != null,
  });

  if (runsQuery.isLoading) return <PageShell subtitle="loading runs…" />;
  if (!latest) {
    return (
      <PageShell subtitle="no completed runs yet">
        <div className="panel px-6 py-10 text-center rise">
          <p className="text-sub mb-4">No benchmark data yet. Launch your first run.</p>
          <Link
            to="/new-run"
            className="inline-block font-mono text-sm border border-s1 text-s1 px-4 py-2 rounded-sm hover:bg-s1 hover:text-page transition-colors"
          >
            START A RUN →
          </Link>
        </div>
      </PageShell>
    );
  }

  const rows = summaryQuery.data ?? [];
  const headline = computeHeadline(rows);
  const multiHopHeadline = computeHeadline(multiHopQuery.data ?? []);

  return (
    <PageShell subtitle={`run #${latest.id} · ${new Date(latest.started_at).toLocaleString()}`}>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <StatTile
          tag="best strategy"
          value={headline.bestStrategy ? strategyLabel(headline.bestStrategy) : "—"}
          detail={`judge ${fmtScore(headline.bestStrategyScore)} / 5`}
          delay={0}
        />
        <StatTile
          tag="lift vs baseline"
          value={headline.bestBaselineGap != null ? `+${fmtScore(headline.bestBaselineGap)}` : "—"}
          detail="judge-score gap to no-retrieval control"
          delay={60}
        />
        <StatTile
          tag="fastest"
          value={headline.fastestStrategy ? strategyLabel(headline.fastestStrategy) : "—"}
          detail={`${fmtLatency(headline.fastestLatencyMs)} avg per question`}
          delay={120}
        />
        <StatTile
          tag="best multi-hop"
          value={multiHopHeadline.bestStrategy ? strategyLabel(multiHopHeadline.bestStrategy) : "—"}
          detail={`judge ${fmtScore(multiHopHeadline.bestStrategyScore)} on multi-hop`}
          delay={180}
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-3 mb-3">
        <GroupedBars
          tag="01 / quality"
          title="Judge score (0–5)"
          rows={rows}
          metric="avg_judge_score"
          domain={[0, 5]}
          delay={200}
        />
        <GroupedBars
          tag="02 / facts"
          title="Keyword recall"
          rows={rows}
          metric="avg_keyword_recall"
          domain={[0, 1]}
          format={(v) => `${Math.round(v * 100)}%`}
          delay={260}
        />
        <GroupedBars
          tag="03 / retrieval"
          title="Retrieval hit rate"
          rows={rows}
          metric="avg_retrieval_hit_rate"
          domain={[0, 1]}
          format={(v) => `${Math.round(v * 100)}%`}
          delay={320}
        />
        <GroupedBars
          tag="04 / cost"
          title="Latency per question"
          rows={rows}
          metric="avg_latency_ms"
          format={(v) => fmtLatency(v)}
          delay={380}
        />
      </div>

      <ScoreHeatmap rows={rows} delay={440} />

      <div className="mt-6 text-right">
        <Link to={`/runs/${latest.id}`} className="text-sm text-s1 hover:underline font-mono">
          drill into run #{latest.id} →
        </Link>
      </div>
    </PageShell>
  );
}

function PageShell({ subtitle, children }: { subtitle: string; children?: React.ReactNode }) {
  return (
    <div>
      <header className="mb-6">
        <div className="section-tag mb-1">results</div>
        <div className="flex items-baseline gap-4">
          <h2 className="text-xl font-semibold">Dashboard</h2>
          <span className="font-mono text-xs text-muted">{subtitle}</span>
        </div>
      </header>
      {children}
    </div>
  );
}
