---
tags: [aurora-mesh, architecture]
---
The data plane is the client-facing gRPC API on port 7432, served by lumen
nodes: reads, writes, and [[Watch Streams]]. Default consistency is
LINEARIZABLE through the raft-lite leader; FOLLOWER_BOUNDED reads accept
staleness bounded by the 45 seconds lease TTL.

Per-lumen limits: 4000 writes per second (then the throttle engages) and
512 concurrent watch streams. Scale by adding lumen nodes — see
[[Node Roles]]. Ports in [[Port Map]].
