---
tags: [aurora-mesh, reference, networking]
---
The four default Aurora Mesh ports:

| Port | Protocol | Purpose |
| ---- | -------- | ------- |
| 7432 | gRPC | client API on the [[Data Plane]] (lumen nodes) |
| 7433 | TCP | [[Control Plane]] — raft-lite and `aurctl` admin |
| 7434 | UDP | [[Glowcast Gossip]] membership |
| 9137 | HTTP | lumenlens metrics exporter, see [[Metrics Catalog]] |

Between nodes open 7433 and 7434; clients need only 7432; keep 9137 on the
monitoring network. #reference
