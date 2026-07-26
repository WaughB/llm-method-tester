"""Deterministic generator for the Aurora Mesh benchmark corpus.

Aurora Mesh is a fictional distributed configuration mesh invented for this
benchmark, so no model can answer from pretraining. Every fact is made up but
kept internally consistent across the plain docs (``corpus/docs``), the
Obsidian-style vault (``corpus/vault``), and the gold Q&A dataset
(``corpus/qa/questions.json``). All content is embedded as literal strings:
no randomness, no timestamps, no network, byte-stable regeneration.
"""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Plain documentation (corpus/docs/*.md)
# ---------------------------------------------------------------------------

_DOC_OVERVIEW = """\
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
"""

_DOC_ARCHITECTURE = """\
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
"""

_DOC_QUICKSTART = """\
# Quickstart

This walkthrough bootstraps a single-machine mesh, writes an entry, and
verifies cluster health. Everything is driven by `aurctl`, the Aurora Mesh
command-line binary.

## Install

### Getting aurctl

Download the `aurctl` binary for your platform and place it on your PATH.
Verify the install with `aurctl version`; you should see release 2.4
(Polaris).

## Initialize the Mesh

### aurctl mesh init

Run `aurctl mesh init` on the first machine. This starts a beacon, creates
the mesh's root namespace, and prints an ember token — the one-time join
credential for other nodes. An ember token is valid for 24 hours; after that
you must mint a new one with `aurctl token mint-ember`.

### Joining Nodes

On each additional machine run `aurctl mesh join --token <ember-token>`.
Joining nodes discover peers either from the token itself or through DNS SRV
records under `_aurora._tcp`. Remember that production meshes need a minimum
of three beacons.

## First Entries

### Writing and Reading

Write your first entry with:

    aurctl put /apps/billing/db-url "postgres://billing-primary:5432/billing"

Entries land in the default namespace, which is named `prism` unless you
override it in configuration. Read it back with
`aurctl get /apps/billing/db-url`. Keep entries small: anything over 768 KB
is rejected with error E-1408.

### Watching

Run `aurctl watch /apps/billing/` to stream every change under a prefix.
Watches ride the same gRPC data-plane port, 7432, that reads and writes use.

## Verify Health

### aurctl mesh doctor

`aurctl mesh doctor` runs a full diagnostic pass: beacon quorum, lease
freshness, glowcast connectivity on UDP 7434, sealbox key age, and lumenlens
exporter reachability on port 9137. A healthy mesh prints `mesh: radiant`.
If doctor reports a lease older than its 45 seconds TTL, check clock skew
first.
"""

_DOC_API_REFERENCE = """\
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
"""

_DOC_CLI_REFERENCE = """\
# CLI Reference

`aurctl` is the single command-line binary for operating Aurora Mesh. It
talks to the data plane on port 7432 for entry operations and to the control
plane on port 7433 for administration.

## Global Flags

### Connection Flags

`--mesh <host:port>` selects the target node, `--namespace` overrides the
default `prism` namespace, and `--token` supplies a glimmer token explicitly.

## Mesh Commands

### aurctl mesh init

Bootstraps a new mesh on the local machine, starts the first beacon, and
prints an ember token that other nodes use to join. The ember token is valid
for 24 hours.

### aurctl mesh join

Joins the local node to an existing mesh using an ember token:
`aurctl mesh join --token <ember-token> --role lumen`.

### aurctl mesh doctor

Runs the full health diagnostic: quorum, leases, glowcast reachability, and
sealbox key age. Exits non-zero if anything is degraded.

## Data Commands

### aurctl put / get / watch

`aurctl put <path> <value>` writes an entry (rejected with E-1408 above
768 KB). `aurctl get <path>` reads, optionally at `--revision`.
`aurctl watch <prefix>` streams changes.

## Node Commands

### aurctl node drain

Puts a node into drain mode: it stops accepting new watch streams, hands off
leases, and exits the gossip ring gracefully. Always drain before stopping a
node during a rolling upgrade.

## Security Commands

### aurctl kiln unlock

Unlocks the kiln keystore after a restart so sealbox can decrypt its master
key. Until the kiln is unlocked, the node serves reads from cache but
refuses writes.

### aurctl token grant

Mints a glimmer token: `aurctl token grant --scope read,write`. The four
scopes are read, write, admin, and audit. Tokens expire after 30 days by
default; pass `--ttl` to shorten (never lengthen) the lifetime.
"""

_DOC_CONFIGURATION = """\
# Configuration

Aurora Mesh reads its configuration from a single TOML file, with every knob
overridable through environment variables.

## The mesh.toml File

### Location

The canonical configuration file is `/etc/aurora/mesh.toml`. A node reads it
once at startup; send `SIGHUP` to reload the dynamic subset.

### Example

    [node]
    role = "lumen"
    data_dir = "/var/lib/aurora"

    [network]
    client_port = 7432
    control_port = 7433
    gossip_port = 7434
    metrics_port = 9137

    [mesh]
    namespace = "prism"
    max_entry_size_kb = 768
    lease_ttl_seconds = 45

## Environment Variables

### Prefix and Precedence

Every key maps to an environment variable with the `AURORA_` prefix, so
`network.client_port` becomes `AURORA_NETWORK_CLIENT_PORT`. Environment
variables win over `/etc/aurora/mesh.toml`, and command-line flags win over
both.

## Defaults Worth Knowing

### Ports

Out of the box a node binds the client API on 7432, the control plane on
7433, glowcast gossip on UDP 7434, and the lumenlens metrics exporter on
9137.

### Namespace

The default namespace is `prism`. Namespaces isolate key paths and glimmer
token grants.

### Leases

The consensus lease TTL is 45 seconds, and holders renew every 15 seconds —
one third of the TTL — so two consecutive renewal failures still leave a
final chance before expiry.

### Entry Cap

`max_entry_size_kb` defaults to 768 KB and is a hard cap: raising it above
768 is rejected at startup to protect replication latency.

## Discovery

### DNS SRV

When no seed list is configured, nodes look up SRV records under
`_aurora._tcp` in the node's search domain and try each target's control
port in priority order.
"""

_DOC_SECURITY = """\
# Security

Aurora Mesh ships with encryption at rest, mutual TLS, and capability-style
tokens enabled by default. There is no plaintext mode.

## Sealbox Envelope Encryption

### How Sealbox Works

Every entry value is encrypted with sealbox, Aurora Mesh's envelope
encryption scheme: a per-entry data key encrypts the value, and the data key
is wrapped by the mesh master key.

### Cipher

Sealbox uses XChaCha20-Poly1305 for both layers of the envelope. Nonces are
derived, never random, so identical plaintexts still produce distinct
ciphertexts across revisions.

### Key Rotation

Sealbox data keys are rotated every 72 hours automatically. Master key
rotation is manual and requires the audit scope.

### The Kiln Keystore

The sealbox master key never touches disk unwrapped: it lives in the kiln
keystore, sealed under an operator passphrase. After a node restart, run
`aurctl kiln unlock` to open the kiln; until then the node refuses writes.

## Transport Security

### Candela CA and mTLS

All inter-node traffic — raft-lite on the control plane, glowcast digests,
and replication streams — uses mTLS with certificates issued by candela, the
mesh's built-in certificate authority. Candela issues short-lived node
certificates and rotates them without restarts.

## Glimmer Tokens

### What They Are

Client and operator authentication uses glimmer tokens: macaroon-style
bearer tokens that can be attenuated offline by appending caveats.

### Scopes

A glimmer token carries one or more of the four scopes: read, write, admin,
and audit. The audit scope is required to read the ledgerstream or rotate
the master key.

### Expiry

Glimmer tokens expire after 30 days by default. Caveats can only shorten a
token's lifetime or narrow its namespace, never extend it.

## Audit

### Ledgerstream

Every administrative action — token grants, drains, key rotations,
membership changes — is recorded by warden nodes into the ledgerstream, an
append-only audit log retained for 90 days. Ledgerstream entries are
themselves sealed with sealbox and require the audit scope to read.
"""

_DOC_REPLICATION = """\
# Replication

This guide covers how Aurora Mesh copies data across the mesh: the
replication factor, consensus leases, snapshots, and tombstone collection.

## Replication Factor

### Defaults

Every entry is stored with a replication factor of five: the raft-lite
leader plus four replicas. Writes are acknowledged after a write quorum of
three replicas have durably applied the entry.

### Placement

Replicas are spread across failure domains when zone labels are configured;
otherwise placement is rack-aware within the gossip topology that glowcast
reports.

## Consensus Leases

### TTL and Renewal

Sessions and leadership claims are guarded by consensus leases. The lease
TTL is 45 seconds, and holders renew every 15 seconds. A lease that reaches
its TTL without renewal is expired by the beacons, and operations using it
fail with error E-2201.

### Why Leases, Not Locks

Leases make failure recovery bounded: a crashed holder blocks others for at
most 45 seconds, and the phi-accrual detector usually reclaims leases much
sooner.

## Snapshots

### Cadence

Beacons snapshot the raft-lite log every 12000 log entries or 10 minutes,
whichever comes first. Snapshots stream to followers through the moonpress
segment format, so a re-seeding follower never replays the full log.

### Retention

Two snapshot generations are kept; older generations are deleted after the
following snapshot commits.

## Tombstones

### Garbage Collection

Deleting an entry writes a tombstone so watches observe the deletion.
Tombstones are garbage collected after 6 hours, which bounds how long a
disconnected watcher can resume without a full re-list.

### Interaction with the Revision Horizon

Tombstone GC never removes revisions still inside the 1000-revision horizon
for a key; the horizon wins.
"""

_DOC_OBSERVABILITY = """\
# Observability

Aurora Mesh exposes metrics through the lumenlens exporter, traces through
OpenTelemetry, and audit events through the ledgerstream.

## Lumenlens Metrics Exporter

### Endpoint

Every node runs lumenlens, the built-in metrics exporter, serving Prometheus
text format on HTTP port 9137 at the `/metrics` path. Lumenlens is
read-only and unauthenticated by default; firewall port 9137 accordingly.

### Key Metrics

The metrics you should alert on first:

- `aurora_apply_latency_seconds` — histogram of raft-lite apply latency.
- `aurora_lease_remaining_seconds` — gauge; alerts fire below 15 seconds.
- `aurora_watch_streams_active` — gauge per lumen; capacity is 512.
- `aurora_gossip_round_duration_seconds` — glowcast round time, nominally
  250 ms.

### Write Throttle Visibility

When a lumen node approaches its 4000 writes per second throttle,
`aurora_write_throttle_engaged` flips to 1 and clients see backpressure.

## Tracing

### OpenTelemetry

All RPCs emit OpenTelemetry spans under the service name `aurora-mesh`.
Sampling defaults to 2% head-based sampling; raise it per-namespace when
debugging.

### Trace Context

Trace context propagates through the `aurora-trace` gRPC metadata key, so a
client span, the lumen data-plane span, and the beacon consensus span join
into one trace.

## Audit Events

### Ledgerstream Access

Warden nodes write every administrative action to the ledgerstream audit
log, retained for 90 days. Read it with `aurctl audit tail`, which requires
a glimmer token carrying the audit scope.

### Shipping Audit Events

Ledgerstream can mirror to an external sink; events remain sealed with
sealbox until they leave the mesh, and the export job appears in the
ledgerstream itself.
"""

_DOC_TROUBLESHOOTING = """\
# Troubleshooting

Start every investigation with `aurctl mesh doctor`, then drill into the
specific symptom below.

## First Steps

### aurctl mesh doctor

Doctor checks beacon quorum, lease freshness against the 45 seconds TTL,
glowcast reachability on UDP 7434, kiln lock state, and the lumenlens
exporter on port 9137. A healthy mesh reports `mesh: radiant`.

## Common Error Codes

### E-2201 LEASE_EXPIRED

A consensus lease passed its 45 seconds TTL without renewal. Usual causes:
GC pauses in the client, clock skew above one second, or a partitioned
holder. The holder must re-acquire; retries with the dead lease will keep
failing.

### E-1408 ENTRY_TOO_LARGE

The write exceeded the 768 KB entry cap. This is a hard limit; store the
payload in object storage and write a reference entry instead.

### E-3301 QUORUM_LOST

Fewer than a write quorum of three beacons are reachable. Check whether
beacons crashed or partitioned; writes stay unavailable until quorum
returns. Follow the lost-quorum runbook rather than force-promoting a
beacon.

## Flapping Membership

### Phi-Accrual Tuning

If nodes oscillate between alive and suspect, inspect the phi-accrual
failure detector. The default suspicion threshold is 8.5; raise it toward
10 on lossy networks, and confirm glowcast rounds are completing near their
250 ms cadence rather than queueing.

## Write Throttling

### Backpressure at 4000 Writes per Second

Each lumen node throttles at 4000 writes per second. If
`aurora_write_throttle_engaged` is set, spread writers across more lumen
nodes or batch small writes; raising the throttle is not supported.

## When the Kiln Is Locked

### Symptoms

After a restart, writes fail while reads succeed. Run `aurctl kiln unlock`
to reopen the keystore so sealbox can unwrap the master key.
"""

_DOC_DEPLOYMENT = """\
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
"""

_DOC_CHANGELOG = """\
# Changelog

Aurora Mesh releases in even minor versions, each with a star codename.

## 2.4 Polaris

### Highlights

The current stable release. Polaris made the phi-accrual threshold (default
8.5) tunable per zone, added derived-nonce mode to sealbox's
XChaCha20-Poly1305 envelope, and taught `aurctl mesh doctor` to verify
lumenlens exporter reachability on port 9137.

### Operational Notes

Rolling upgrade from 2.2 Meridian is supported, one beacon at a time. The
ember token format changed; tokens minted by 2.2 remain valid for their full
24 hours.

## 2.2 Meridian

### Highlights

Meridian introduced the warden role and the ledgerstream audit log with its
90-day retention, raised the watch stream ceiling to 512 per lumen node, and
moved gossip to glowcast v2 with a fanout of six peers every 250 ms.

### Deprecations

The legacy `aurmesh` binary name was removed; the CLI is `aurctl` only.

## 2.0 Halcyon

### Highlights

Halcyon was the first generally available release: raft-lite consensus with
a replication factor of five, the moonpress storage engine, sealbox envelope
encryption with 72-hour data-key rotation, glimmer tokens with four scopes,
and the candela certificate authority for mesh-wide mTLS.

### Known Issues

Halcyon shipped with a 384 KB entry cap; 2.2 Meridian raised it to the
current 768 KB.
"""

_DOC_GLOSSARY = """\
# Glossary

Definitions for every Aurora Mesh term of art, grouped by area.

## Consensus and Membership Terms

### raft-lite

The trimmed consensus protocol run by beacon nodes: Raft-style leadership
with pre-vote and joint consensus fused into one round trip.

### glowcast

The gossip protocol for membership and failure detection, running on UDP
port 7434 with a fanout of six peers every 250 ms.

### phi-accrual detector

The adaptive failure detector fed by glowcast timing samples; nodes are
suspected above the default threshold of 8.5.

### consensus lease

A time-bounded claim with a 45 seconds TTL, renewed every 15 seconds;
expiry surfaces as error E-2201.

## Node Roles

### lumen

The data-plane role: serves reads, writes, and watch streams on port 7432.

### beacon

The consensus voter role: minimum of three, maximum of nine per mesh.

### warden

The policy and audit role: writes the ledgerstream audit log.

## Security Terms

### sealbox

The envelope encryption scheme (XChaCha20-Poly1305) protecting every entry
value; data keys rotate every 72 hours.

### kiln

The keystore holding the sealed master key; opened with
`aurctl kiln unlock`.

### candela

The built-in certificate authority issuing the mTLS certificates for all
inter-node traffic.

### glimmer token

A macaroon-style bearer token with scopes read, write, admin, and audit;
expires after 30 days.

### ember token

The one-time join credential printed by `aurctl mesh init`, valid for
24 hours.

## Storage Terms

### moonpress

The log-structured storage engine; segments live under `/var/lib/aurora`.

### revision horizon

The 1000 revisions retained per key for historical reads and watch resume.

### ledgerstream

The append-only audit log written by wardens and retained for 90 days.

### prism

The default namespace for key paths and token grants.
"""

_DOCS: dict[str, str] = {
    "docs/overview.md": _DOC_OVERVIEW,
    "docs/architecture.md": _DOC_ARCHITECTURE,
    "docs/quickstart.md": _DOC_QUICKSTART,
    "docs/api-reference.md": _DOC_API_REFERENCE,
    "docs/cli-reference.md": _DOC_CLI_REFERENCE,
    "docs/configuration.md": _DOC_CONFIGURATION,
    "docs/security.md": _DOC_SECURITY,
    "docs/replication.md": _DOC_REPLICATION,
    "docs/observability.md": _DOC_OBSERVABILITY,
    "docs/troubleshooting.md": _DOC_TROUBLESHOOTING,
    "docs/deployment.md": _DOC_DEPLOYMENT,
    "docs/changelog.md": _DOC_CHANGELOG,
    "docs/glossary.md": _DOC_GLOSSARY,
}

# ---------------------------------------------------------------------------
# Obsidian-style vault notes (corpus/vault/<Folder>/<Title>.md)
# ---------------------------------------------------------------------------

_NOTE_GLOWCAST = """\
---
tags: [aurora-mesh, gossip, networking]
---
Glowcast is Aurora Mesh's gossip protocol for membership and failure
detection. It runs over UDP port 7434 — see [[Port Map]] for the full port
list.

Mechanics: each round a node picks a fanout of six peers and swaps digests,
and rounds fire every 250 ms. Rumors cover a nine-node mesh in under two
seconds. Glowcast carries membership state, timing samples for the
[[Phi-Accrual Failure Detection]] detector, and lease hints — never actual
config data, which belongs to [[Raft-Lite Consensus]] on the
[[Control Plane]].
"""

_NOTE_RAFT_LITE = """\
---
tags: [aurora-mesh, consensus]
---
Raft-lite is the trimmed consensus protocol at the heart of Aurora Mesh:
Raft-style single leadership, but pre-vote and joint consensus are fused
into one round trip. Only [[Node Roles|beacon]] nodes vote — minimum of
three, maximum of nine.

The replicated log is compacted by snapshot every 12000 log entries or
10 minutes, whichever comes first; lagging followers re-seed from the
snapshot. Leadership and sessions are guarded by [[Consensus Leases]], and
replica placement is covered in [[Replication Topology]]. #consensus
"""

_NOTE_LEASES = """\
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
"""

_NOTE_SEALBOX = """\
---
tags: [aurora-mesh, security, encryption]
---
Sealbox is Aurora Mesh's envelope encryption scheme: a per-entry data key
encrypts each value, and the data key is wrapped by the mesh master key.
Both layers use XChaCha20-Poly1305 with derived (never random) nonces.

Data keys are rotated every 72 hours automatically; master key rotation is
manual — see [[Rotate Sealbox Keys]]. The master key lives sealed in the
kiln keystore and is opened with `aurctl kiln unlock` after restarts.
Related: [[Glimmer Tokens]], [[Security Model]]. #encryption
"""

_NOTE_GLIMMER = """\
---
tags: [aurora-mesh, security, auth]
---
Glimmer tokens are Aurora Mesh's macaroon-style bearer tokens: they can be
attenuated offline by appending caveats, which only ever narrow (never
extend) what a token can do.

A token carries one or more of the four scopes: read, write, admin, and
audit. The audit scope gates the ledgerstream and master-key rotation.
Default expiry is 30 days. Minted via `aurctl token grant` — see
[[aurctl CLI]]. Values they protect are sealed by [[Sealbox Encryption]].
"""

_NOTE_ROLES = """\
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
"""

_NOTE_WATCH = """\
---
tags: [aurora-mesh, api]
---
Watch streams are server-streaming gRPC RPCs on the [[Data Plane]] port
7432 that deliver ordered change events for a key or prefix. Events are
never dropped while inside the 1000-revision horizon.

Each lumen node serves at most 512 concurrent watch streams; the 513th gets
RESOURCE_EXHAUSTED, so spread watchers across lumen nodes. Start one from
the CLI with `aurctl watch` — see [[aurctl CLI]]. Resume after disconnects
is bounded by tombstone GC (6 hours).
"""

_NOTE_MOONPRESS = """\
---
tags: [aurora-mesh, storage]
---
Moonpress is Aurora Mesh's log-structured storage engine. Lumen and beacon
nodes persist moonpress segments under `/var/lib/aurora`, and a background
compactor rewrites cold segments.

Moonpress retains a revision horizon of 1000 revisions per key for
historical reads and watch resume; older revisions fold away during
compaction and tombstones are garbage collected after 6 hours. Snapshots
from [[Raft-Lite Consensus]] stream in moonpress segment format — see
[[Replication Topology]]. #storage
"""

_NOTE_PHI = """\
---
tags: [aurora-mesh, gossip, reliability]
---
Aurora Mesh replaces fixed heartbeats with a phi-accrual failure detector
fed by [[Glowcast Gossip]] timing samples. A node is marked suspect when
its phi value crosses the default threshold of 8.5; raise it toward 10 on
lossy networks.

Suspicion is advisory — actual membership changes still require a quorum
decision by the beacons. Draining a node first (`aurctl node drain`) avoids
spurious suspicion during [[Rolling Upgrade]]s.
"""

_NOTE_PORT_MAP = """\
---
tags: [aurora-mesh, reference, networking]
---
The four default Aurora Mesh ports:

| Port | Protocol | Purpose |
| ---- | -------- | ------- |
| 7432 | gRPC | client API on the [[Data Plane]] (lumen nodes) |
| 7433 | TCP | [[Control Plane]] — raft-lite and `aurctl` admin |
| 7434 | UDP | [[Glowcast Gossip]] membership |
| 9137 | HTTP | lumenlens metrics exporter, see [[Metrics Catalog]] |

Between nodes open 7433 and 7434; clients need only 7432; keep 9137 on the
monitoring network. #reference
"""

_NOTE_AURCTL = """\
---
tags: [aurora-mesh, reference, cli]
---
`aurctl` is the one CLI binary for Aurora Mesh (the legacy `aurmesh` name
died in 2.2 Meridian). Commands I actually use:

- `aurctl mesh init` — bootstrap; prints the ember token ([[Bootstrap a Mesh]])
- `aurctl mesh join --token ...` — join a node
- `aurctl mesh doctor` — health check; healthy prints `mesh: radiant`
- `aurctl put` / `aurctl get` / `aurctl watch` — entry operations
- `aurctl node drain` — hand off leases before stopping ([[Rolling Upgrade]])
- `aurctl kiln unlock` — open the keystore after restart
- `aurctl token grant --scope read,write` — mint [[Glimmer Tokens]]
- `aurctl audit tail` — read the ledgerstream
"""

_NOTE_MESH_TOML = """\
---
tags: [aurora-mesh, reference, config]
---
Defaults from `/etc/aurora/mesh.toml` worth memorizing:

- namespace: `prism`
- max entry size: 768 KB (hard cap — startup rejects anything larger)
- lease TTL: 45 seconds, renewed every 15 seconds ([[Consensus Leases]])
- data dir: `/var/lib/aurora`
- ports: see [[Port Map]]

Environment variables use the `AURORA_` prefix (e.g.
`AURORA_NETWORK_CLIENT_PORT`) and beat the file; flags beat both. With no
seed list, discovery falls back to DNS SRV under `_aurora._tcp`. #config
"""

_NOTE_ERROR_CODES = """\
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
"""

_NOTE_RELEASES = """\
---
tags: [aurora-mesh, reference, releases]
---
Aurora Mesh release line (even minors, star codenames):

- **2.4 Polaris** — current; tunable phi threshold, derived-nonce
  [[Sealbox Encryption]], doctor checks lumenlens.
- **2.2 Meridian** — warden role + ledgerstream, [[Watch Streams]] ceiling
  raised to 512, glowcast v2, entry cap raised to 768 KB.
- **2.0 Halcyon** — first GA: raft-lite, moonpress, sealbox, glimmer
  tokens, candela CA.

Upgrades roll one beacon at a time. #releases
"""

_NOTE_METRICS = """\
---
tags: [aurora-mesh, reference, observability]
---
Lumenlens is the built-in metrics exporter: Prometheus text format on HTTP
port 9137 at `/metrics` (unauthenticated — firewall it; see [[Port Map]]).

Alert-first metrics:

- `aurora_apply_latency_seconds` — raft-lite apply latency histogram
- `aurora_lease_remaining_seconds` — page below 15 seconds
- `aurora_watch_streams_active` — capacity 512 per lumen
- `aurora_write_throttle_engaged` — lumen at its 4000 writes per second cap

Traces: OpenTelemetry, service name `aurora-mesh`, 2% sampling. #metrics
"""

_NOTE_KEY_PATHS = """\
---
tags: [aurora-mesh, reference]
---
Key path rules in Aurora Mesh: slash-delimited UTF-8, at most 12 segments,
at most 256 bytes total. Trailing slash means prefix operation (used by
[[Watch Streams]]).

Paths live inside a namespace (default `prism`). Every write returns a
revision; history is readable inside the 1000-revision horizon kept by
[[Moonpress Compaction]]. Oversized values are a different failure — that's
E-1408 in [[Error Codes]], the 768 KB entry cap.
"""

_NOTE_BOOTSTRAP = """\
---
tags: [aurora-mesh, runbook]
---
Bootstrapping a new mesh:

1. `aurctl mesh init` on the first box — starts a beacon and prints the
   ember token (valid for 24 hours; re-mint with `aurctl token mint-ember`).
2. `aurctl mesh join --token <ember-token> --role lumen` on each other
   node; discovery also works via `_aurora._tcp` SRV records.
3. Grow beacons to the production floor — [[Node Roles]] says three
   beacons, two lumens, one warden.
4. `aurctl mesh doctor` until it prints `mesh: radiant`.

See [[aurctl CLI]] for every command. #runbook
"""

_NOTE_ROTATE_KEYS = """\
---
tags: [aurora-mesh, runbook, security]
---
Sealbox data keys rotate themselves every 72 hours — no action needed.
Master key rotation is manual and needs a glimmer token with the audit
scope.

Procedure: verify mesh health, run the rotation from a warden, then confirm
the new key generation in the ledgerstream. After any node restart the kiln
keystore comes up locked: run `aurctl kiln unlock` or the node will refuse
writes while serving stale reads. Details in [[Sealbox Encryption]];
command syntax in [[aurctl CLI]]. #runbook
"""

_NOTE_RECOVER_QUORUM = """\
---
tags: [aurora-mesh, runbook, incident]
---
Symptom: writes fail with E-3301 (QUORUM_LOST) — fewer than a write quorum
of three beacons reachable. Reads may still work in FOLLOWER_BOUNDED mode.

1. `aurctl mesh doctor` — count live beacons.
2. Check [[Glowcast Gossip]] reachability on UDP 7434 between beacons.
3. Restart crashed beacons; never force-promote a lone survivor.
4. Once [[Raft-Lite Consensus]] regains a minimum of three voters, leases
   re-establish within their 45 seconds TTL.

Error taxonomy in [[Error Codes]]. #runbook #incident
"""

_NOTE_ROLLING_UPGRADE = """\
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
"""

_NOTE_AUDIT_REVIEW = """\
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
"""

_NOTE_CONTROL_PLANE = """\
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
"""

_NOTE_DATA_PLANE = """\
---
tags: [aurora-mesh, architecture]
---
The data plane is the client-facing gRPC API on port 7432, served by lumen
nodes: reads, writes, and [[Watch Streams]]. Default consistency is
LINEARIZABLE through the raft-lite leader; FOLLOWER_BOUNDED reads accept
staleness bounded by the 45 seconds lease TTL.

Per-lumen limits: 4000 writes per second (then the throttle engages) and
512 concurrent watch streams. Scale by adding lumen nodes — see
[[Node Roles]]. Ports in [[Port Map]].
"""

_NOTE_REPLICATION_TOPOLOGY = """\
---
tags: [aurora-mesh, architecture, replication]
---
Every entry is stored with a replication factor of five — the raft-lite
leader plus four replicas — and writes are acknowledged after a write
quorum of three durably apply. Placement spreads replicas across failure
domains reported by [[Glowcast Gossip]].

Snapshots happen every 12000 log entries or 10 minutes and stream in
[[Moonpress Compaction]] segment format. Deletions leave tombstones,
garbage collected after 6 hours, never inside a key's 1000-revision
horizon. Consensus details in [[Raft-Lite Consensus]]. #replication
"""

_NOTE_SECURITY_MODEL = """\
---
tags: [aurora-mesh, architecture, security]
---
Aurora Mesh's security stack, bottom to top:

- **[[Sealbox Encryption|sealbox]]** — envelope encryption
  (XChaCha20-Poly1305) for every entry value; data keys rotate every
  72 hours.
- **kiln** — the keystore sealing the master key; `aurctl kiln unlock`
  after restarts.
- **candela** — built-in CA issuing short-lived certs; all inter-node
  traffic is mTLS.
- **[[Glimmer Tokens|glimmer]]** — macaroon-style tokens, scopes read /
  write / admin / audit, 30-day expiry.

No plaintext mode exists. Audit trail: ledgerstream, per
[[Audit Log Review]]. #security
"""

_NOTES: dict[str, str] = {
    "vault/Concepts/Glowcast Gossip.md": _NOTE_GLOWCAST,
    "vault/Concepts/Raft-Lite Consensus.md": _NOTE_RAFT_LITE,
    "vault/Concepts/Consensus Leases.md": _NOTE_LEASES,
    "vault/Concepts/Sealbox Encryption.md": _NOTE_SEALBOX,
    "vault/Concepts/Glimmer Tokens.md": _NOTE_GLIMMER,
    "vault/Concepts/Node Roles.md": _NOTE_ROLES,
    "vault/Concepts/Watch Streams.md": _NOTE_WATCH,
    "vault/Concepts/Moonpress Compaction.md": _NOTE_MOONPRESS,
    "vault/Concepts/Phi-Accrual Failure Detection.md": _NOTE_PHI,
    "vault/Reference/Port Map.md": _NOTE_PORT_MAP,
    "vault/Reference/aurctl CLI.md": _NOTE_AURCTL,
    "vault/Reference/mesh.toml Defaults.md": _NOTE_MESH_TOML,
    "vault/Reference/Error Codes.md": _NOTE_ERROR_CODES,
    "vault/Reference/Release History.md": _NOTE_RELEASES,
    "vault/Reference/Metrics Catalog.md": _NOTE_METRICS,
    "vault/Reference/Key Path Rules.md": _NOTE_KEY_PATHS,
    "vault/Runbooks/Bootstrap a Mesh.md": _NOTE_BOOTSTRAP,
    "vault/Runbooks/Rotate Sealbox Keys.md": _NOTE_ROTATE_KEYS,
    "vault/Runbooks/Recover Lost Quorum.md": _NOTE_RECOVER_QUORUM,
    "vault/Runbooks/Rolling Upgrade.md": _NOTE_ROLLING_UPGRADE,
    "vault/Runbooks/Audit Log Review.md": _NOTE_AUDIT_REVIEW,
    "vault/Architecture/Control Plane.md": _NOTE_CONTROL_PLANE,
    "vault/Architecture/Data Plane.md": _NOTE_DATA_PLANE,
    "vault/Architecture/Replication Topology.md": _NOTE_REPLICATION_TOPOLOGY,
    "vault/Architecture/Security Model.md": _NOTE_SECURITY_MODEL,
}

# ---------------------------------------------------------------------------
# Gold Q&A dataset (corpus/qa/questions.json)
# ---------------------------------------------------------------------------

_QUESTIONS: list[dict[str, object]] = [
    # -- single_hop ---------------------------------------------------------
    {
        "id": "sh-01",
        "question": "Which TCP port does the Aurora Mesh control plane listen on?",
        "category": "single_hop",
        "expected_keywords": [["7433"]],
        "source_docs": ["docs/configuration.md"],
        "source_notes": ["vault/Reference/Port Map.md"],
        "gold_answer": "The control plane listens on TCP port 7433.",
    },
    {
        "id": "sh-02",
        "question": "What is the name of Aurora Mesh's gossip protocol?",
        "category": "single_hop",
        "expected_keywords": [["glowcast"]],
        "source_docs": ["docs/architecture.md"],
        "source_notes": ["vault/Concepts/Glowcast Gossip.md"],
        "gold_answer": "The gossip protocol is called glowcast; it runs over UDP port 7434.",
    },
    {
        "id": "sh-03",
        "question": "What is the default consensus lease TTL in Aurora Mesh?",
        "category": "single_hop",
        "expected_keywords": [["45 seconds"]],
        "source_docs": ["docs/replication.md"],
        "source_notes": ["vault/Concepts/Consensus Leases.md"],
        "gold_answer": "The consensus lease TTL is 45 seconds.",
    },
    {
        "id": "sh-04",
        "question": "What is the maximum size of a single configuration entry?",
        "category": "single_hop",
        "expected_keywords": [["768 KB", "768"]],
        "source_docs": ["docs/configuration.md"],
        "source_notes": ["vault/Reference/mesh.toml Defaults.md"],
        "gold_answer": "A configuration entry is capped at 768 KB.",
    },
    {
        "id": "sh-05",
        "question": "What is the name of the Aurora Mesh command-line binary?",
        "category": "single_hop",
        "expected_keywords": [["aurctl"]],
        "source_docs": ["docs/cli-reference.md"],
        "source_notes": ["vault/Reference/aurctl CLI.md"],
        "gold_answer": "The command-line binary is aurctl.",
    },
    {
        "id": "sh-06",
        "question": "What is the name of Aurora Mesh's envelope encryption scheme?",
        "category": "single_hop",
        "expected_keywords": [["sealbox"]],
        "source_docs": ["docs/security.md"],
        "source_notes": ["vault/Concepts/Sealbox Encryption.md"],
        "gold_answer": "Entry values are protected by the sealbox envelope encryption scheme.",
    },
    {
        "id": "sh-07",
        "question": "What is the default namespace in Aurora Mesh?",
        "category": "single_hop",
        "expected_keywords": [["prism"]],
        "source_docs": ["docs/configuration.md"],
        "source_notes": ["vault/Reference/mesh.toml Defaults.md"],
        "gold_answer": "The default namespace is prism.",
    },
    {
        "id": "sh-08",
        "question": "Which AEAD cipher does sealbox use for its envelope layers?",
        "category": "single_hop",
        "expected_keywords": [["XChaCha20-Poly1305", "xchacha20"]],
        "source_docs": ["docs/security.md"],
        "source_notes": ["vault/Concepts/Sealbox Encryption.md"],
        "gold_answer": "Sealbox uses XChaCha20-Poly1305 for both envelope layers.",
    },
    {
        "id": "sh-09",
        "question": "On which port does the lumenlens metrics exporter serve /metrics?",
        "category": "single_hop",
        "expected_keywords": [["9137"]],
        "source_docs": ["docs/observability.md"],
        "source_notes": ["vault/Reference/Metrics Catalog.md"],
        "gold_answer": "The lumenlens exporter serves Prometheus metrics on HTTP port 9137.",
    },
    {
        "id": "sh-10",
        "question": "Which error code does Aurora Mesh return when a consensus lease expires?",
        "category": "single_hop",
        "expected_keywords": [["E-2201"]],
        "source_docs": ["docs/troubleshooting.md"],
        "source_notes": ["vault/Reference/Error Codes.md"],
        "gold_answer": "An expired consensus lease surfaces as error E-2201 (LEASE_EXPIRED).",
    },
    {
        "id": "sh-11",
        "question": "Where is the canonical Aurora Mesh configuration file located?",
        "category": "single_hop",
        "expected_keywords": [["/etc/aurora/mesh.toml", "mesh.toml"]],
        "source_docs": ["docs/configuration.md"],
        "source_notes": ["vault/Reference/mesh.toml Defaults.md"],
        "gold_answer": "The canonical configuration file is /etc/aurora/mesh.toml.",
    },
    {
        "id": "sh-12",
        "question": "What is the name of Aurora Mesh's storage engine?",
        "category": "single_hop",
        "expected_keywords": [["moonpress"]],
        "source_docs": ["docs/architecture.md"],
        "source_notes": ["vault/Concepts/Moonpress Compaction.md"],
        "gold_answer": "Nodes persist state in the moonpress log-structured storage engine.",
    },
    {
        "id": "sh-13",
        "question": "What is the codename of the Aurora Mesh 2.4 release?",
        "category": "single_hop",
        "expected_keywords": [["Polaris"]],
        "source_docs": ["docs/changelog.md"],
        "source_notes": ["vault/Reference/Release History.md"],
        "gold_answer": "Release 2.4 is codenamed Polaris.",
    },
    {
        "id": "sh-14",
        "question": "Where do warden nodes record administrative audit events?",
        "category": "single_hop",
        "expected_keywords": [["ledgerstream"]],
        "source_docs": ["docs/security.md"],
        "source_notes": ["vault/Runbooks/Audit Log Review.md"],
        "gold_answer": (
            "Wardens write every administrative action to the ledgerstream audit log, "
            "retained for 90 days."
        ),
    },
    # -- multi_hop ----------------------------------------------------------
    {
        "id": "mh-01",
        "question": (
            "Which port serves Aurora Mesh client API traffic, and what secures "
            "inter-node traffic on the other planes?"
        ),
        "category": "multi_hop",
        "expected_keywords": [["7432"], ["candela"], ["mTLS", "mutual TLS"]],
        "source_docs": ["docs/api-reference.md", "docs/security.md"],
        "source_notes": [
            "vault/Reference/Port Map.md",
            "vault/Architecture/Security Model.md",
        ],
        "gold_answer": (
            "Clients use the gRPC API on port 7432, while inter-node traffic is "
            "protected by mTLS with certificates issued by the candela CA."
        ),
    },
    {
        "id": "mh-02",
        "question": ("What is the consensus lease TTL, and how often do holders renew it?"),
        "category": "multi_hop",
        "expected_keywords": [["45 seconds"], ["15 seconds"]],
        "source_docs": ["docs/replication.md", "docs/configuration.md"],
        "source_notes": ["vault/Concepts/Consensus Leases.md"],
        "gold_answer": (
            "The lease TTL is 45 seconds and holders renew every 15 seconds, one third of the TTL."
        ),
    },
    {
        "id": "mh-03",
        "question": (
            "Which command bootstraps a new mesh, and how long is the join "
            "credential it prints valid?"
        ),
        "category": "multi_hop",
        "expected_keywords": [["aurctl mesh init", "mesh init"], ["24 hours"]],
        "source_docs": ["docs/quickstart.md", "docs/cli-reference.md"],
        "source_notes": ["vault/Runbooks/Bootstrap a Mesh.md"],
        "gold_answer": (
            "aurctl mesh init bootstraps the mesh and prints an ember token that "
            "is valid for 24 hours."
        ),
    },
    {
        "id": "mh-04",
        "question": (
            "What is Aurora Mesh's default replication factor, and how many "
            "replicas must acknowledge a write?"
        ),
        "category": "multi_hop",
        "expected_keywords": [["replication factor of five"], ["write quorum of three"]],
        "source_docs": ["docs/replication.md"],
        "source_notes": ["vault/Architecture/Replication Topology.md"],
        "gold_answer": (
            "Entries use a replication factor of five, and writes are acknowledged "
            "after a write quorum of three replicas durably apply."
        ),
    },
    {
        "id": "mh-05",
        "question": (
            "Where is the sealbox master key stored, and which command unlocks it "
            "after a node restart?"
        ),
        "category": "multi_hop",
        "expected_keywords": [["kiln"], ["kiln unlock"]],
        "source_docs": ["docs/security.md", "docs/cli-reference.md"],
        "source_notes": ["vault/Runbooks/Rotate Sealbox Keys.md"],
        "gold_answer": (
            "The master key lives sealed in the kiln keystore, opened with "
            "aurctl kiln unlock after a restart."
        ),
    },
    {
        "id": "mh-06",
        "question": (
            "How many peers does glowcast contact each gossip round, and how often do rounds fire?"
        ),
        "category": "multi_hop",
        "expected_keywords": [["fanout of six"], ["250 ms"]],
        "source_docs": ["docs/architecture.md"],
        "source_notes": ["vault/Concepts/Glowcast Gossip.md"],
        "gold_answer": (
            "Each round glowcast picks a fanout of six peers, and rounds fire every 250 ms."
        ),
    },
    {
        "id": "mh-07",
        "question": (
            "Which error is returned when an entry exceeds the size cap, and what is that cap?"
        ),
        "category": "multi_hop",
        "expected_keywords": [["E-1408"], ["768 KB", "768"]],
        "source_docs": ["docs/api-reference.md", "docs/configuration.md"],
        "source_notes": [
            "vault/Reference/Error Codes.md",
            "vault/Reference/mesh.toml Defaults.md",
        ],
        "gold_answer": (
            "Writes larger than the 768 KB entry cap fail with error E-1408 (ENTRY_TOO_LARGE)."
        ),
    },
    {
        "id": "mh-08",
        "question": (
            "How often are sealbox data keys rotated, and how long do glimmer "
            "tokens live by default?"
        ),
        "category": "multi_hop",
        "expected_keywords": [["72 hours"], ["30 days"]],
        "source_docs": ["docs/security.md"],
        "source_notes": [
            "vault/Concepts/Sealbox Encryption.md",
            "vault/Concepts/Glimmer Tokens.md",
        ],
        "gold_answer": (
            "Sealbox data keys rotate every 72 hours, and glimmer tokens expire "
            "after 30 days by default."
        ),
    },
    {
        "id": "mh-09",
        "question": "What triggers a raft-lite snapshot in Aurora Mesh?",
        "category": "multi_hop",
        "expected_keywords": [["12000"], ["10 minutes"]],
        "source_docs": ["docs/replication.md", "docs/architecture.md"],
        "source_notes": ["vault/Concepts/Raft-Lite Consensus.md"],
        "gold_answer": (
            "A snapshot is taken every 12000 log entries or 10 minutes, whichever comes first."
        ),
    },
    {
        "id": "mh-10",
        "question": (
            "What mechanism detects node failures in Aurora Mesh, and at what "
            "default threshold does it mark a node suspect?"
        ),
        "category": "multi_hop",
        "expected_keywords": [["phi-accrual"], ["8.5"]],
        "source_docs": ["docs/architecture.md", "docs/troubleshooting.md"],
        "source_notes": ["vault/Concepts/Phi-Accrual Failure Detection.md"],
        "gold_answer": (
            "A phi-accrual failure detector fed by glowcast marks nodes suspect "
            "above the default threshold of 8.5."
        ),
    },
    # -- aggregation --------------------------------------------------------
    {
        "id": "ag-01",
        "question": "List all three Aurora Mesh node roles.",
        "category": "aggregation",
        "expected_keywords": [["lumen"], ["beacon"], ["warden"]],
        "source_docs": ["docs/overview.md"],
        "source_notes": ["vault/Concepts/Node Roles.md"],
        "gold_answer": "The three node roles are lumen, beacon, and warden.",
    },
    {
        "id": "ag-02",
        "question": "List all four scopes a glimmer token can carry.",
        "category": "aggregation",
        "expected_keywords": [["read"], ["write"], ["admin"], ["audit"]],
        "source_docs": ["docs/security.md", "docs/cli-reference.md"],
        "source_notes": ["vault/Concepts/Glimmer Tokens.md"],
        "gold_answer": "The four glimmer token scopes are read, write, admin, and audit.",
    },
    {
        "id": "ag-03",
        "question": "List the codenames of the three Aurora Mesh 2.x releases.",
        "category": "aggregation",
        "expected_keywords": [["Polaris"], ["Meridian"], ["Halcyon"]],
        "source_docs": ["docs/changelog.md"],
        "source_notes": ["vault/Reference/Release History.md"],
        "gold_answer": ("The 2.x releases are 2.4 Polaris, 2.2 Meridian, and 2.0 Halcyon."),
    },
    {
        "id": "ag-04",
        "question": "List all four default network ports Aurora Mesh uses.",
        "category": "aggregation",
        "expected_keywords": [["7432"], ["7433"], ["7434"], ["9137"]],
        "source_docs": ["docs/overview.md", "docs/configuration.md"],
        "source_notes": ["vault/Reference/Port Map.md"],
        "gold_answer": (
            "The default ports are 7432 (client API), 7433 (control plane), 7434 "
            "(glowcast gossip), and 9137 (lumenlens metrics)."
        ),
    },
    {
        "id": "ag-05",
        "question": "List the three documented Aurora Mesh error codes.",
        "category": "aggregation",
        "expected_keywords": [["E-2201"], ["E-1408"], ["E-3301"]],
        "source_docs": ["docs/troubleshooting.md"],
        "source_notes": ["vault/Reference/Error Codes.md"],
        "gold_answer": (
            "The documented error codes are E-2201 (lease expired), E-1408 (entry "
            "too large), and E-3301 (quorum lost)."
        ),
    },
    {
        "id": "ag-06",
        "question": (
            "Name the four components of the Aurora Mesh security stack: the "
            "envelope scheme, the keystore, the certificate authority, and the "
            "token system."
        ),
        "category": "aggregation",
        "expected_keywords": [["sealbox"], ["kiln"], ["candela"], ["glimmer"]],
        "source_docs": ["docs/security.md"],
        "source_notes": ["vault/Architecture/Security Model.md"],
        "gold_answer": (
            "The security stack is sealbox envelope encryption, the kiln keystore, "
            "the candela certificate authority, and glimmer tokens."
        ),
    },
]


def generate(root: Path) -> None:
    """Write the full benchmark corpus under `root`: docs/, vault/, qa/questions.json."""
    files = dict(_DOCS)
    files.update(_NOTES)
    files["qa/questions.json"] = json.dumps(_QUESTIONS, indent=2) + "\n"
    for rel_path, content in files.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
