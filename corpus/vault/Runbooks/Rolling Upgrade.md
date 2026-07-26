---
tags: [aurora-mesh, runbook, operations]
---
Rolling upgrade order: wardens, then lumens, then beacons — beacons
strictly one at a time so quorum never dips below three voters.

Per node: `aurctl node drain` (hands off leases, stops new watch streams,
announces departure via glowcast so [[Phi-Accrual Failure Detection]] stays
quiet), stop, upgrade, rejoin, then wait for `aurctl mesh doctor` to print
`mesh: radiant` before touching the next one. Commands in [[aurctl CLI]];
role order rationale in [[Node Roles]]. #runbook
