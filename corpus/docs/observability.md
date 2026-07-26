# Observability

Aurora Mesh exposes metrics through the lumenlens exporter, traces through
OpenTelemetry, and audit events through the ledgerstream.

## Lumenlens Metrics Exporter

### Endpoint

Every node runs lumenlens, the built-in metrics exporter, serving Prometheus
text format on HTTP port 9137 at the `/metrics` path. Lumenlens is
read-only and unauthenticated by default; firewall port 9137 accordingly.

### Key Metrics

The metrics you should alert on first:

- `aurora_apply_latency_seconds` — histogram of raft-lite apply latency.
- `aurora_lease_remaining_seconds` — gauge; alerts fire below 15 seconds.
- `aurora_watch_streams_active` — gauge per lumen; capacity is 512.
- `aurora_gossip_round_duration_seconds` — glowcast round time, nominally
  250 ms.

### Write Throttle Visibility

When a lumen node approaches its 4000 writes per second throttle,
`aurora_write_throttle_engaged` flips to 1 and clients see backpressure.

## Tracing

### OpenTelemetry

All RPCs emit OpenTelemetry spans under the service name `aurora-mesh`.
Sampling defaults to 2% head-based sampling; raise it per-namespace when
debugging.

### Trace Context

Trace context propagates through the `aurora-trace` gRPC metadata key, so a
client span, the lumen data-plane span, and the beacon consensus span join
into one trace.

## Audit Events

### Ledgerstream Access

Warden nodes write every administrative action to the ledgerstream audit
log, retained for 90 days. Read it with `aurctl audit tail`, which requires
a glimmer token carrying the audit scope.

### Shipping Audit Events

Ledgerstream can mirror to an external sink; events remain sealed with
sealbox until they leave the mesh, and the export job appears in the
ledgerstream itself.
