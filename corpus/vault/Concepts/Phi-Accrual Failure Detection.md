---
tags: [aurora-mesh, gossip, reliability]
---
Aurora Mesh replaces fixed heartbeats with a phi-accrual failure detector
fed by [[Glowcast Gossip]] timing samples. A node is marked suspect when
its phi value crosses the default threshold of 8.5; raise it toward 10 on
lossy networks.

Suspicion is advisory — actual membership changes still require a quorum
decision by the beacons. Draining a node first (`aurctl node drain`) avoids
spurious suspicion during [[Rolling Upgrade]]s.
