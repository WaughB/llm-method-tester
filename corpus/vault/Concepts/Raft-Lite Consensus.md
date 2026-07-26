---
tags: [aurora-mesh, consensus]
---
Raft-lite is the trimmed consensus protocol at the heart of Aurora Mesh:
Raft-style single leadership, but pre-vote and joint consensus are fused
into one round trip. Only [[Node Roles|beacon]] nodes vote — minimum of
three, maximum of nine.

The replicated log is compacted by snapshot every 12000 log entries or
10 minutes, whichever comes first; lagging followers re-seed from the
snapshot. Leadership and sessions are guarded by [[Consensus Leases]], and
replica placement is covered in [[Replication Topology]]. #consensus
