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
