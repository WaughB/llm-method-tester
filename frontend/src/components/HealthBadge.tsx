import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export function HealthBadge() {
  const { data, isLoading } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 15000,
  });
  const ok = data?.ok ?? false;
  return (
    <div className="flex items-center gap-2">
      <span
        aria-hidden
        className={`inline-block w-2 h-2 rounded-full ${
          isLoading ? "bg-muted animate-pulse" : ok ? "bg-good" : "bg-critical"
        }`}
      />
      <div className="text-xs">
        <div className="text-sub">{isLoading ? "checking…" : ok ? "Ollama online" : "Ollama offline"}</div>
        {ok && <div className="font-mono text-[10px] text-muted">{data?.models.length} models</div>}
      </div>
    </div>
  );
}
