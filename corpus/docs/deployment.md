# Deployment

This guide covers sizing, discovery, upgrades, and storage layout for
production meshes.

## Sizing

### Minimum Production Cluster

A production mesh needs three beacons, two lumens, and one warden. Beacons
must number a minimum of three for quorum and a maximum of nine; more than
nine voters slows raft-lite elections without improving fault tolerance.

### Scaling Reads and Watches

Add lumen nodes to scale reads and watch streams; each lumen node caps at
512 concurrent watch streams and 4000 writes per second. Beacon count
should stay odd.

## Discovery

### DNS SRV Records

Publish each node's control-plane endpoint as an SRV record under
`_aurora._tcp`. Joining nodes resolve the record set and dial targets on
port 7433 in priority order.

## Rolling Upgrades

### One Beacon at a Time

Upgrade wardens first, then lumens, then beacons — and beacons strictly one
at a time so quorum never dips below three voters. Wait for
`aurctl mesh doctor` to report `mesh: radiant` between beacons.

### Drain Mode

Before stopping any node, run `aurctl node drain`. Draining hands off
leases, stops new watch streams, and announces departure through glowcast so
the phi-accrual detector does not mark the node suspect.

## Storage

### Data Directory

Nodes persist moonpress segments under `/var/lib/aurora`. Provision fast
local storage; snapshots (every 12000 log entries or 10 minutes) create
short write bursts.

### Backups

Back up by copying the latest snapshot generation plus the kiln-sealed
master key export. Never back up the unlocked kiln.

## Network Policy

### Ports to Open

Between nodes: 7433 (control plane, mTLS via candela) and UDP 7434
(glowcast). From clients: 7432. From your monitoring network only: 9137
(lumenlens).
