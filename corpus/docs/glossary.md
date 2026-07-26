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
