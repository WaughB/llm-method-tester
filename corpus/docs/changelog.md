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
