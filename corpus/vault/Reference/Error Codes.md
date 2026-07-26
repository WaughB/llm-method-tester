---
tags: [aurora-mesh, reference, errors]
---
The three Aurora Mesh error codes that page people:

- **E-2201 LEASE_EXPIRED** — a [[Consensus Leases|consensus lease]] passed
  its 45 seconds TTL unrenewed; re-acquire, don't retry blindly.
- **E-1408 ENTRY_TOO_LARGE** — value over the 768 KB cap; store a
  reference instead.
- **E-3301 QUORUM_LOST** — fewer than a write quorum of three beacons
  reachable; go to [[Recover Lost Quorum]].

#errors
