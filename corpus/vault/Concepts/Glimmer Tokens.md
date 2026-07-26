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
