# Replication

This guide covers how Aurora Mesh copies data across the mesh: the
replication factor, consensus leases, snapshots, and tombstone collection.

## Replication Factor

### Defaults

Every entry is stored with a replication factor of five: the raft-lite
leader plus four replicas. Writes are acknowledged after a
write quorum of three replicas have durably applied the entry.

### Placement

Replicas are spread across failure domains when zone labels are configured;
otherwise placement is rack-aware within the gossip topology that glowcast
reports.

## Consensus Leases

### TTL and Renewal

Sessions and leadership claims are guarded by consensus leases. The lease
TTL is 45 seconds, and holders renew every 15 seconds. A lease that reaches
its TTL without renewal is expired by the beacons, and operations using it
fail with error E-2201.

### Why Leases, Not Locks

Leases make failure recovery bounded: a crashed holder blocks others for at
most 45 seconds, and the phi-accrual detector usually reclaims leases much
sooner.

## Snapshots

### Cadence

Beacons snapshot the raft-lite log every 12000 log entries or 10 minutes,
whichever comes first. Snapshots stream to followers through the moonpress
segment format, so a re-seeding follower never replays the full log.

### Retention

Two snapshot generations are kept; older generations are deleted after the
following snapshot commits.

## Tombstones

### Garbage Collection

Deleting an entry writes a tombstone so watches observe the deletion.
Tombstones are garbage collected after 6 hours, which bounds how long a
disconnected watcher can resume without a full re-list.

### Interaction with the Revision Horizon

Tombstone GC never removes revisions still inside the 1000-revision horizon
for a key; the horizon wins.
