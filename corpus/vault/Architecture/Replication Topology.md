---
tags: [aurora-mesh, architecture, replication]
---
Every entry is stored with a replication factor of five — the raft-lite
leader plus four replicas — and writes are acknowledged after a
write quorum of three durably apply. Placement spreads replicas across failure
domains reported by [[Glowcast Gossip]].

Snapshots happen every 12000 log entries or 10 minutes and stream in
[[Moonpress Compaction]] segment format. Deletions leave tombstones,
garbage collected after 6 hours, never inside a key's 1000-revision
horizon. Consensus details in [[Raft-Lite Consensus]]. #replication
