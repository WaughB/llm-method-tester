---
tags: [aurora-mesh, api]
---
Watch streams are server-streaming gRPC RPCs on the [[Data Plane]] port
7432 that deliver ordered change events for a key or prefix. Events are
never dropped while inside the 1000-revision horizon.

Each lumen node serves at most 512 concurrent watch streams; the 513th gets
RESOURCE_EXHAUSTED, so spread watchers across lumen nodes. Start one from
the CLI with `aurctl watch` — see [[aurctl CLI]]. Resume after disconnects
is bounded by tombstone GC (6 hours).
