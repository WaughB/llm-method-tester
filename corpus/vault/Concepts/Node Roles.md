---
tags: [aurora-mesh, architecture, roles]
---
Every Aurora Mesh process runs exactly one of three roles:

- **lumen** — data plane: reads, writes, watch streams on port 7432; caps
  at 4000 writes per second and 512 watch streams. See [[Data Plane]].
- **beacon** — consensus voter for [[Raft-Lite Consensus]]; a mesh needs a
  minimum of three beacons and allows a maximum of nine.
- **warden** — policy and audit; writes the ledgerstream reviewed in
  [[Audit Log Review]].

Production floor: three beacons, two lumens, one warden. #roles
