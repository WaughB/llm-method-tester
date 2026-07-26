import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { CATEGORY_LABELS, strategyLabel } from "../lib/format";

export default function NewRun() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const questions = useQuery({ queryKey: ["questions"], queryFn: api.questions });

  const [models, setModels] = useState<Set<string>>(new Set());
  const [strategies, setStrategies] = useState<Set<string>>(new Set());
  const [categories, setCategories] = useState<Set<string>>(new Set());

  const start = useMutation({
    mutationFn: api.startRun,
    onSuccess: ({ run_id }) => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      navigate(`/runs/${run_id}`);
    },
  });

  if (meta.isLoading || questions.isLoading) {
    return <p className="text-sub">loading configuration…</p>;
  }
  if (!meta.data || !questions.data) {
    return <p className="text-critical">Could not load /api/meta — is the backend running?</p>;
  }

  const questionIds =
    categories.size === 0
      ? undefined
      : questions.data.filter((q) => categories.has(q.category)).map((q) => q.id);
  const selectedCount = questionIds?.length ?? meta.data.question_count;
  const cellCount =
    (models.size || meta.data.models.length) *
    (strategies.size || meta.data.strategies.length) *
    selectedCount;

  return (
    <div className="max-w-2xl">
      <header className="mb-6">
        <div className="section-tag mb-1">launcher</div>
        <h2 className="text-xl font-semibold">New run</h2>
      </header>

      <PickerSection
        tag="models"
        hint="none selected = all"
        options={meta.data.models}
        selected={models}
        onToggle={(v) => setModels(toggle(models, v))}
        render={(v) => <span className="font-mono">{v}</span>}
      />
      <PickerSection
        tag="strategies"
        hint="none selected = all"
        options={meta.data.strategies}
        selected={strategies}
        onToggle={(v) => setStrategies(toggle(strategies, v))}
        render={(v) => strategyLabel(v)}
      />
      <PickerSection
        tag="question categories"
        hint={`none selected = all ${meta.data.question_count} questions`}
        options={Object.keys(CATEGORY_LABELS)}
        selected={categories}
        onToggle={(v) => setCategories(toggle(categories, v))}
        render={(v) => CATEGORY_LABELS[v]}
      />

      <div className="panel px-5 py-4 mt-6 flex items-center justify-between rise">
        <div className="text-sm text-sub">
          <span className="font-mono text-ink">{cellCount}</span> cells (
          {models.size || meta.data.models.length} models ×{" "}
          {strategies.size || meta.data.strategies.length} strategies × {selectedCount} questions)
          + judging
        </div>
        <button
          onClick={() =>
            start.mutate({
              models: models.size ? [...models] : undefined,
              strategies: strategies.size ? [...strategies] : undefined,
              question_ids: questionIds,
            })
          }
          disabled={start.isPending}
          className="font-mono text-sm border border-s1 text-s1 px-5 py-2 rounded-sm hover:bg-s1 hover:text-page transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {start.isPending ? "LAUNCHING…" : "LAUNCH →"}
        </button>
      </div>
      {start.isError && (
        <p role="alert" className="mt-3 text-sm text-critical">
          {(start.error as Error).message}
        </p>
      )}
    </div>
  );
}

function toggle(set: Set<string>, value: string): Set<string> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

function PickerSection({
  tag,
  hint,
  options,
  selected,
  onToggle,
  render,
}: {
  tag: string;
  hint: string;
  options: string[];
  selected: Set<string>;
  onToggle: (value: string) => void;
  render: (value: string) => React.ReactNode;
}) {
  return (
    <section className="mb-5 rise">
      <div className="flex items-baseline gap-3 mb-2">
        <div className="section-tag">{tag}</div>
        <span className="text-[11px] text-muted">{hint}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const active = selected.has(option);
          return (
            <button
              key={option}
              onClick={() => onToggle(option)}
              aria-pressed={active}
              className={`text-sm px-3 py-1.5 rounded-sm border transition-colors ${
                active
                  ? "border-s1 bg-s1/15 text-ink"
                  : "border-hairline text-sub hover:border-muted"
              }`}
            >
              {render(option)}
            </button>
          );
        })}
      </div>
    </section>
  );
}
