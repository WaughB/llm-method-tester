---
tags: [aurora-mesh, reference, observability]
---
Lumenlens is the built-in metrics exporter: Prometheus text format on HTTP
port 9137 at `/metrics` (unauthenticated — firewall it; see [[Port Map]]).

Alert-first metrics:

- `aurora_apply_latency_seconds` — raft-lite apply latency histogram
- `aurora_lease_remaining_seconds` — page below 15 seconds
- `aurora_watch_streams_active` — capacity 512 per lumen
- `aurora_write_throttle_engaged` — lumen at its 4000 writes per second cap

Traces: OpenTelemetry, service name `aurora-mesh`, 2% sampling. #metrics
