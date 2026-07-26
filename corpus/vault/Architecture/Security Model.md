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
