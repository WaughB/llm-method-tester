---
tags: [aurora-mesh, gossip, networking]
---
Glowcast is Aurora Mesh's gossip protocol for membership and failure
detection. It runs over UDP port 7434 — see [[Port Map]] for the full port
list.

Mechanics: each round a node picks a fanout of six peers and swaps digests,
and rounds fire every 250 ms. Rumors cover a nine-node mesh in under two
seconds. Glowcast carries membership state, timing samples for the
[[Phi-Accrual Failure Detection]] detector, and lease hints — never actual
config data, which belongs to [[Raft-Lite Consensus]] on the
[[Control Plane]].
