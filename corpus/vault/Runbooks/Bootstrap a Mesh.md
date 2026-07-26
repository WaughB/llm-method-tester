---
tags: [aurora-mesh, runbook]
---
Bootstrapping a new mesh:

1. `aurctl mesh init` on the first box — starts a beacon and prints the
   ember token (valid for 24 hours; re-mint with `aurctl token mint-ember`).
2. `aurctl mesh join --token <ember-token> --role lumen` on each other
   node; discovery also works via `_aurora._tcp` SRV records.
3. Grow beacons to the production floor — [[Node Roles]] says three
   beacons, two lumens, one warden.
4. `aurctl mesh doctor` until it prints `mesh: radiant`.

See [[aurctl CLI]] for every command. #runbook
