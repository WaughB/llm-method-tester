# Aurora Mesh Architecture

This guide explains how the pieces of a mesh fit together: the two network
planes, the raft-lite consensus core, the glowcast gossip layer, and the
moonpress storage engine.

## Planes

Aurora Mesh strictly separates administrative traffic from application
traffic.

### Control Plane

The control plane listens on TCP port 7433. Beacons exchange raft-lite
messages here, and `aurctl` administrative commands (membership changes,
draining, key rotation) terminate here. Control-plane traffic is always
wrapped in mTLS using certificates issued by the built-in candela CA.

### Data Plane

The data plane is the client-facing gRPC API on port 7432, served by lumen
nodes. Reads, writes, and watch streams all use this port. Each lumen node
enforces a write throttle of 4000 writes per second and a ceiling of 512
concurrent watch streams.

## Consensus with Raft-Lite

Raft-lite is Aurora Mesh's trimmed consensus protocol: single-decree
leadership like Raft, but with pre-vote and joint-consensus phases fused into
one round trip.

### Leader Election

Only beacon nodes vote. A mesh requires a minimum of three beacons and allows
a maximum of nine; elections complete in a single round trip in the common
case.

### Log and Snapshots

The replicated log is compacted by snapshot: a snapshot is taken every 12000
log entries or 10 minutes, whichever comes first. Followers that fall behind
the snapshot horizon are re-seeded from the latest snapshot.

### Failure Detection

Beacons do not use fixed heartbeats to declare peers dead. Aurora Mesh runs a
phi-accrual failure detector fed by glowcast gossip observations, with a
default suspicion threshold of 8.5. Crossing the threshold marks a node
suspect; consensus membership changes still require a quorum decision.

## Glowcast Gossip

Glowcast is the mesh's membership and dissemination protocol. It runs over
UDP port 7434.

### Fanout and Rounds

Every gossip round, a node picks a fanout of six peers and exchanges digests
with them. Rounds fire every 250 ms, so rumors reach a nine-node mesh in well
under two seconds.

### What Glowcast Carries

Glowcast carries membership state, phi-accrual timing samples, and lease
ownership hints. It never carries configuration data; that is raft-lite's
job.

## Storage Engine

### Moonpress Compaction

Lumen and beacon nodes persist state in the moonpress storage engine, a
log-structured store whose compactor rewrites cold segments in the
background. Data lives under `/var/lib/aurora` by default.

### Revision Horizon

Moonpress retains a revision horizon of 1000 revisions per key. Older
revisions are folded away during compaction, and tombstones are garbage
collected after 6 hours.
