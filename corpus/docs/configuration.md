# Configuration

Aurora Mesh reads its configuration from a single TOML file, with every knob
overridable through environment variables.

## The mesh.toml File

### Location

The canonical configuration file is `/etc/aurora/mesh.toml`. A node reads it
once at startup; send `SIGHUP` to reload the dynamic subset.

### Example

    [node]
    role = "lumen"
    data_dir = "/var/lib/aurora"

    [network]
    client_port = 7432
    control_port = 7433
    gossip_port = 7434
    metrics_port = 9137

    [mesh]
    namespace = "prism"
    max_entry_size_kb = 768
    lease_ttl_seconds = 45

## Environment Variables

### Prefix and Precedence

Every key maps to an environment variable with the `AURORA_` prefix, so
`network.client_port` becomes `AURORA_NETWORK_CLIENT_PORT`. Environment
variables win over `/etc/aurora/mesh.toml`, and command-line flags win over
both.

## Defaults Worth Knowing

### Ports

Out of the box a node binds the client API on 7432, the control plane on
7433, glowcast gossip on UDP 7434, and the lumenlens metrics exporter on
9137.

### Namespace

The default namespace is `prism`. Namespaces isolate key paths and glimmer
token grants.

### Leases

The consensus lease TTL is 45 seconds, and holders renew every 15 seconds —
one third of the TTL — so two consecutive renewal failures still leave a
final chance before expiry.

### Entry Cap

`max_entry_size_kb` defaults to 768 KB and is a hard cap: raising it above
768 is rejected at startup to protect replication latency.

## Discovery

### DNS SRV

When no seed list is configured, nodes look up SRV records under
`_aurora._tcp` in the node's search domain and try each target's control
port in priority order.
