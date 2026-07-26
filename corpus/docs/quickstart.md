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
