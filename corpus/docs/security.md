# Security

Aurora Mesh ships with encryption at rest, mutual TLS, and capability-style
tokens enabled by default. There is no plaintext mode.

## Sealbox Envelope Encryption

### How Sealbox Works

Every entry value is encrypted with sealbox, Aurora Mesh's envelope
encryption scheme: a per-entry data key encrypts the value, and the data key
is wrapped by the mesh master key.

### Cipher

Sealbox uses XChaCha20-Poly1305 for both layers of the envelope. Nonces are
derived, never random, so identical plaintexts still produce distinct
ciphertexts across revisions.

### Key Rotation

Sealbox data keys are rotated every 72 hours automatically. Master key
rotation is manual and requires the audit scope.

### The Kiln Keystore

The sealbox master key never touches disk unwrapped: it lives in the kiln
keystore, sealed under an operator passphrase. After a node restart, run
`aurctl kiln unlock` to open the kiln; until then the node refuses writes.

## Transport Security

### Candela CA and mTLS

All inter-node traffic — raft-lite on the control plane, glowcast digests,
and replication streams — uses mTLS with certificates issued by candela, the
mesh's built-in certificate authority. Candela issues short-lived node
certificates and rotates them without restarts.

## Glimmer Tokens

### What They Are

Client and operator authentication uses glimmer tokens: macaroon-style
bearer tokens that can be attenuated offline by appending caveats.

### Scopes

A glimmer token carries one or more of the four scopes: read, write, admin,
and audit. The audit scope is required to read the ledgerstream or rotate
the master key.

### Expiry

Glimmer tokens expire after 30 days by default. Caveats can only shorten a
token's lifetime or narrow its namespace, never extend it.

## Audit

### Ledgerstream

Every administrative action — token grants, drains, key rotations,
membership changes — is recorded by warden nodes into the ledgerstream, an
append-only audit log retained for 90 days. Ledgerstream entries are
themselves sealed with sealbox and require the audit scope to read.
