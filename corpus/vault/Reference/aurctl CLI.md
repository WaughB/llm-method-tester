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
