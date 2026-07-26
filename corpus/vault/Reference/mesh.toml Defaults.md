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
