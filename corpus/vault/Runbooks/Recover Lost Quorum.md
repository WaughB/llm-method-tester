---
tags: [aurora-mesh, runbook, incident]
---
Symptom: writes fail with E-3301 (QUORUM_LOST) — fewer than a write quorum
of three beacons reachable. Reads may still work in FOLLOWER_BOUNDED mode.

1. `aurctl mesh doctor` — count live beacons.
2. Check [[Glowcast Gossip]] reachability on UDP 7434 between beacons.
3. Restart crashed beacons; never force-promote a lone survivor.
4. Once [[Raft-Lite Consensus]] regains a minimum of three voters, leases
   re-establish within their 45 seconds TTL.

Error taxonomy in [[Error Codes]]. #runbook #incident
