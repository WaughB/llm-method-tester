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
