import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { StorageLocation } from "../api/types";

function formatBytes(bytes: number | null): string {
  if (bytes == null) return "—";
  const gb = bytes / 1024 ** 3;
  return gb >= 1000 ? `${(gb / 1024).toFixed(1)} TB` : `${gb.toFixed(0)} GB`;
}

export default function Settings() {
  const queryClient = useQueryClient();
  const locations = useQuery({ queryKey: ["locations"], queryFn: api.locations });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });

  const activate = useMutation({
    mutationFn: api.activateLocation,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["locations"] }),
  });
  const update = useMutation({
    mutationFn: api.updateSettings,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["settings"] }),
  });

  return (
    <div className="max-w-2xl">
      <header className="mb-6">
        <div className="section-tag mb-1">configuration</div>
        <h2 className="text-xl font-semibold">Settings</h2>
      </header>

      <section className="mb-8">
        <div className="section-tag mb-3">storage location</div>
        {locations.isLoading && <p className="text-sub text-sm">probing mounts…</p>}
        <div className="space-y-2">
          {locations.data?.map((location) => (
            <LocationCard
              key={location.location_id}
              location={location}
              onActivate={() => activate.mutate(location.location_id)}
              activating={activate.isPending}
            />
          ))}
        </div>
        {activate.isError && (
          <p role="alert" className="mt-2 text-sm text-critical">
            {(activate.error as Error).message}
          </p>
        )}
        <p className="mt-3 text-[11px] text-muted">
          Locations are host directories listed in .env (PIT_ROOT_0, PIT_ROOT_1). Each keeps its
          own independent library — switching never moves data.
        </p>
      </section>

      <section>
        <div className="section-tag mb-3">answering model</div>
        {settings.data && (
          <div className="flex items-center gap-3">
            <input
              aria-label="default model"
              className="bg-surface border border-hairline rounded-sm px-3 py-2 font-mono text-sm w-64 focus:border-s1 outline-none"
              defaultValue={settings.data.default_model}
              onBlur={(event) => {
                const value = event.target.value.trim();
                if (value && value !== settings.data!.default_model) {
                  update.mutate({ default_model: value });
                }
              }}
            />
            {update.isPending && <span className="text-xs text-muted">saving…</span>}
          </div>
        )}
        <p className="mt-2 text-[11px] text-muted">
          Any model pulled in Ollama. Changes apply to new questions immediately.
        </p>
      </section>
    </div>
  );
}

function LocationCard({
  location,
  onActivate,
  activating,
}: {
  location: StorageLocation;
  onActivate: () => void;
  activating: boolean;
}) {
  return (
    <div
      className={`panel px-4 py-3 flex items-center justify-between ${
        location.active ? "border-s1" : ""
      } ${location.available ? "" : "opacity-60"}`}
    >
      <div>
        <div className="font-mono text-sm">{location.host_label}</div>
        <div className="text-[11px] text-muted mt-0.5">
          {location.available
            ? `${formatBytes(location.free_bytes)} free of ${formatBytes(location.total_bytes)}`
            : "unavailable — is the drive mounted and shared with Docker?"}
        </div>
      </div>
      {location.active ? (
        <span className="font-mono text-[10px] uppercase tracking-widest text-s1 border border-s1/50 px-2 py-1 rounded-sm">
          active
        </span>
      ) : (
        <button
          onClick={onActivate}
          disabled={!location.available || activating}
          className="font-mono text-xs border border-hairline text-sub px-3 py-1.5 rounded-sm hover:border-s1 hover:text-s1 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          ACTIVATE
        </button>
      )}
    </div>
  );
}
