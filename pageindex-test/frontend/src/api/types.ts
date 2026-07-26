// Mirrors the pageindex-test FastAPI schemas. Grows with each phase.

export interface HealthCheck {
  ok: boolean;
  error?: string;
  models?: string[];
  missing?: string[];
}

export interface Meta {
  version: string;
  default_model: string;
  ok: boolean;
  checks: Record<string, HealthCheck>;
}

export interface StorageLocation {
  location_id: string;
  host_label: string;
  available: boolean;
  free_bytes: number | null;
  total_bytes: number | null;
  active: boolean;
}

export interface AppSettings {
  default_model: string;
  hybrid_top_n: number;
  tree_stage_docs: number;
  use_pageindex_stage: boolean;
}
