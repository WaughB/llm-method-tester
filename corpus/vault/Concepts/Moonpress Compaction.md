---
tags: [aurora-mesh, storage]
---
Moonpress is Aurora Mesh's log-structured storage engine. Lumen and beacon
nodes persist moonpress segments under `/var/lib/aurora`, and a background
compactor rewrites cold segments.

Moonpress retains a revision horizon of 1000 revisions per key for
historical reads and watch resume; older revisions fold away during
compaction and tombstones are garbage collected after 6 hours. Snapshots
from [[Raft-Lite Consensus]] stream in moonpress segment format — see
[[Replication Topology]]. #storage
