---
tags: [aurora-mesh, architecture]
---
The control plane is Aurora Mesh's administrative network: TCP port 7433.
[[Raft-Lite Consensus]] messages between beacons, membership changes,
drains, and `aurctl` admin calls all terminate here.

Control-plane traffic is always mTLS, with certificates issued by candela
(the built-in CA) — see [[Security Model]]. Discovery publishes
control-plane endpoints as `_aurora._tcp` SRV records. Strictly separate
from the [[Data Plane]]; full listing in [[Port Map]].
