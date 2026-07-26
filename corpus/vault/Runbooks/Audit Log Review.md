---
tags: [aurora-mesh, runbook, audit]
---
Warden nodes record every administrative action — token grants, drains, key
rotations, membership changes — to the ledgerstream, an append-only audit
log retained for 90 days and sealed with sealbox.

Reading it requires a glimmer token with the audit scope:
`aurctl audit tail`. During review, cross-check drains against
[[Rolling Upgrade]] tickets and key rotations against
[[Rotate Sealbox Keys]]. The warden role itself is described in
[[Node Roles]]. #audit
