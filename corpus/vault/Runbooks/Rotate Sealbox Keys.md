---
tags: [aurora-mesh, runbook, security]
---
Sealbox data keys rotate themselves every 72 hours — no action needed.
Master key rotation is manual and needs a glimmer token with the audit
scope.

Procedure: verify mesh health, run the rotation from a warden, then confirm
the new key generation in the ledgerstream. After any node restart the kiln
keystore comes up locked: run `aurctl kiln unlock` or the node will refuse
writes while serving stale reads. Details in [[Sealbox Encryption]];
command syntax in [[aurctl CLI]]. #runbook
