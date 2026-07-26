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
