---
tags: [aurora-mesh, consensus, leases]
---
Consensus leases guard sessions and leadership claims in Aurora Mesh. The
lease TTL is 45 seconds and holders renew every 15 seconds (one third of the
TTL), so two missed renewals still leave one last chance.

When a lease passes its TTL without renewal the beacons expire it and
operations fail with error E-2201 (LEASE_EXPIRED) — see [[Error Codes]].
A crashed holder therefore blocks others for at most 45 seconds, usually
less thanks to [[Phi-Accrual Failure Detection]]. Part of
[[Raft-Lite Consensus]].
