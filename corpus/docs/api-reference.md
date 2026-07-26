# API Reference

The Aurora Mesh client API is gRPC, served by lumen nodes on port 7432.
Administrative RPCs live on the control plane, TCP port 7433, and require a
glimmer token with the admin scope.

## Transport

### Endpoints

Clients dial any lumen node on port 7432. Connections are load-balanced
per-RPC, and every RPC carries a glimmer token in the `aurora-token`
metadata header.

### Consistency Modes

`LINEARIZABLE` (default) routes through the raft-lite leader.
`FOLLOWER_BOUNDED` allows reads from any lumen with staleness bounded by the
lease TTL of 45 seconds.

## Key Paths

### Rules

Key paths are slash-delimited UTF-8 strings. A path may have at most 12
segments and at most 256 bytes total length. Trailing slashes denote prefix
operations.

## Entries

### Size Limits

An entry value may be at most 768 KB. Oversized writes fail with error
E-1408 (`ENTRY_TOO_LARGE`) before reaching consensus.

### Revisions

Every write returns a revision number. Historical reads may reference any
revision inside the 1000-revision horizon.

## Watch Streams

### Semantics

`Watch` opens a server-streaming RPC that delivers ordered change events for
a key or prefix. Events are never dropped inside the revision horizon.

### Limits

Each lumen node serves at most 512 concurrent watch streams. The 513th
stream is rejected with `RESOURCE_EXHAUSTED`; spread watchers across lumen
nodes.

## Errors

### E-2201 LEASE_EXPIRED

The session's consensus lease passed its 45 seconds TTL without renewal.
Re-acquire the lease and retry.

### E-1408 ENTRY_TOO_LARGE

The entry value exceeded the 768 KB cap. Store the blob elsewhere and write
a reference.

### E-3301 QUORUM_LOST

Fewer than a write quorum of three beacons are reachable. Writes are
unavailable until quorum is restored; reads may continue in
`FOLLOWER_BOUNDED` mode.
