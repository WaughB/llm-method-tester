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
