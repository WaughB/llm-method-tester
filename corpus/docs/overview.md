# Aurora Mesh Overview

Aurora Mesh is a distributed configuration mesh: a replicated, strongly
consistent store for typed configuration entries that applications read and
watch at runtime. The current stable release is 2.4, codenamed Polaris. A
mesh is a set of cooperating nodes that agree on every configuration change
through the raft-lite consensus protocol and disseminate membership state
through the glowcast gossip protocol.

## What Aurora Mesh Does

### A Configuration Mesh, Not a Database

Aurora Mesh stores small, versioned configuration entries under slash-delimited
key paths such as `/apps/billing/db-url`. Entries are capped at 768 KB each,
which keeps replication cheap and forces large blobs into object storage where
they belong. Every write is assigned a monotonically increasing revision, and
the mesh keeps a revision horizon of 1000 revisions per key for time-travel
reads and diff-based watches.

### Strict Linearizability

There are no CRDTs and no eventual-consistency modes in Aurora Mesh. All
writes flow through the current raft-lite leader, so a successful write is
immediately visible to every linearizable read. Clients that can tolerate
bounded staleness may opt into follower reads, but the default is strict.

## The Three Node Roles

Every process in a mesh runs as exactly one of three roles.

### Lumen

A lumen node serves the data plane: client reads, writes, and watch streams.
Each lumen node sustains up to 4000 writes per second before the write
throttle engages, and holds up to 512 concurrent watch streams.

### Beacon

A beacon node is a consensus voter. Beacons run raft-lite, elect the leader,
and store the replicated log. A mesh needs a minimum of three beacons and
supports a maximum of nine.

### Warden

A warden node enforces policy and records every administrative action to the
ledgerstream audit log, which is retained for 90 days.

## Network Ports at a Glance

Aurora Mesh uses four well-known ports out of the box:

- **7432** — client API (gRPC), served by lumen nodes on the data plane.
- **7433** — control plane (TCP), used by beacons and `aurctl` admin calls.
- **7434** — glowcast gossip (UDP), membership and failure detection.
- **9137** — lumenlens metrics exporter (HTTP, Prometheus format).

## Where to Go Next

Read the Quickstart to bootstrap a three-node mesh with `aurctl mesh init`,
then the Architecture guide for how raft-lite, glowcast, and the moonpress
storage engine fit together. The Security guide covers sealbox envelope
encryption, the candela certificate authority, and glimmer access tokens.
