# RUNBOOK — restore durable Eldyrwild World authority

Local recovery of the exact Eldyrwild DungeonMind World Graph. This is not
remote hosting, HA, or a Buddy graph fallback.

Keep `compose.postgres.yml` for disposable tests. It uses `tmpfs` and is
ephemeral. This runbook uses `compose.postgres.authority.yml` and a named
volume.

The DSN is authority. The database name is not.

## Separate DSNs

```text
DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL
  postgresql://dungeonmind:<compose-password>@127.0.0.1:54330/dungeonmind_cutover_live

DUNGEONBUDDY_APPLICATION_STATE_DATABASE_URL
  postgresql://dungeonmind:<compose-password>@127.0.0.1:54329/dungeonbuddy_application_state
```

Passwords come from the compose files / local env. Do not commit a secret-bearing DSN.

Do not point both at the same logical database. Do not use the ephemeral
`127.0.0.1:54329/dungeonmind` database as living World authority.

## Accepted recovery input

CHECKPOINT A identified the exact dump:

```text
/home/drakosfire/Projects/DungeonOverMind/.env-backup/eldyrwild-v4-repair-20260823T215423Z/dungeonmind_cutover_live.dump
SHA-256 a7d126b88b72400d208572e20d02226acbe84887af9d8b69cdcae4ba99c8f617
```

That dump is operator-local. Do not commit it. The restore command refuses a
file whose digest does not match.

### CHECKPOINT A ledger — last-known-head proof

WR1 §3/§11 require a pre-mutation ledger proving (a) the exact D_B recovery
input and (b) that no later authoritative Eldyrwild head exists. Recorded
2026-09-06 against the restored authority.

**Recovery input (a).** The accepted dump above is the exact D_B-bearing
durable representation. Its sidecars in the same operator folder record the
post-repair identity:

- `SHA256SUMS` pins the dump digest (`a7d126b8…`) and the pre-repair identity.
- `post-repair-identity.json` records head `rev:680c246047d67f9fe0293ee90526f670`,
  `revision_ids = [D_A, D_B]`, `contribution_count = 95`, and the v4 receipt
  wrapper (`membership_sha256 = M0 = 538195e3…`,
  `effective_membership_sha256 = M1 = 16d3161d…`).
- `pre-repair-identity.json` records the same head/contribution count with the
  v3 receipt (`membership_sha256 = 16d3161d…`), matching the dump's stored
  receipt.

**No-later-head search (b).** D_B is hardcoded as the recovery target, so the
absence of any later authoritative head is part of the safety argument. Sources
searched for a later published Eldyrwild revision (any revision naming D_B as
parent, or any newer head):

- DungeonMind checked-in authority: `benchmarks/world_graph_live_postgres.py`
  (`EXPECTED_HEAD = D_B`), `Docs/Reports/K0-surface-inventory.json` (live
  authority head `D_B`, parent `D_A`).
- Buddy checked-in authority: `HANDOFF-CUTOVER-whole-world-authority-transfer.md`,
  `HANDOFF-CUTOVER-native-read-switch.md`, `HANDOFF-CUTOVER-r3-read-contract-ratification.md`,
  `PR-TRACKER-campaign-supergraph.md`, `STATUS-world-graph-continuity-spine.md`,
  `STEWARDS-ANCHOR-cutover.md`, `ROADMAP-campaign-supergraph.md`,
  `BASELINE-r3-direct-dungeonmind-current-reads.md` — all record head `D_B`,
  parent `D_A`, CUTOVER_COMPLETE.
- Text search across both repositories for any revision declaring
  `parent_revision_id = rev:680c246…` (a child of D_B): **none found**.
- Surviving database state: the only surviving Eldyrwild database artifact is
  the accepted dump itself; the ephemeral `127.0.0.1:54329/dungeonmind` database
  is empty (tmpfs, development-only). No other dump/volume/backup survives.

**Conclusion.** No later authoritative Eldyrwild head than
`D_B = rev:680c246047d67f9fe0293ee90526f670` was found in any checked-in
authority record, governed publication receipt, or surviving durable artifact.
The accepted dump is the last recoverable authority and is the accepted
recovery input. Had a later head been found, this lane would STOP and rebrief
on that lineage instead of restoring D_B.

Expected lineage after restore + migrate:

```text
world_id = eldyrwild
D_A      = rev:34b1f8e2625d5ba693fc726a2a1a4720
D_B/head = rev:680c246047d67f9fe0293ee90526f670
parent(D_B) = D_A
```

The accepted dump stores receipt schema `dm_existing_world_adoption_receipt_v3`
with `membership_sha256` equal to the post-repair digest:

```text
16d3161d270691460ccbf6d183055ad9f29f00bdbecf5c26dfe0189da2b9914e
```

A sidecar in the same operator folder records the later v4 wrapper
(`M0` sealed-bundle membership, `M1` the digest above). Preflight accepts
either shape. Do not rewrite the restored dump receipt into v4.

Preflight does not trust that stored digest. It derives the adopted-member
manifest from the sealed bundle fixture
(`tests/fixtures/dungeonmind_dnd/eldyrwild_existing_world_adoption_bundle_v2.json`),
fetches each adopted durable record by id, recomputes the canonical
`dm_existing_world_adoption_membership_v1` digest, and requires it to equal the
receipt's sanctioned checkpoint (M0 on a fresh adoption, M1 on the repaired
dump). Same-cardinality substitution — mutating a durable record's payload
while keeping its id, the counts, and the receipt — fails closed. Preflight
also enforces the accepted projection cardinality: the D_B projection must
contain exactly 469 objects.

Do not restore the sealed adoption bundle and call D_A current.

## Bootstrap

From the DungeonMind repository:

```bash
docker compose -f compose.postgres.authority.yml up -d
export DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL='postgresql://dungeonmind:dungeonmind-dev@127.0.0.1:54330/dungeonmind_cutover_live'

uv run python scripts/eldyrwild_world_authority_recovery.py restore \
  --database-url "$DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL" \
  --dump-path /home/drakosfire/Projects/DungeonOverMind/.env-backup/eldyrwild-v4-repair-20260823T215423Z/dungeonmind_cutover_live.dump
```

`restore` runs `pg_restore`, then `alembic upgrade head`, then `check`.
`READY` is required before Buddy dogfood.

Check only:

```bash
uv run python scripts/eldyrwild_world_authority_recovery.py check \
  --database-url "$DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL" \
  --expected-head rev:680c246047d67f9fe0293ee90526f670
```

## Ordinary restart

```bash
docker compose -f compose.postgres.authority.yml down
docker compose -f compose.postgres.authority.yml up -d
uv run python scripts/eldyrwild_world_authority_recovery.py check \
  --database-url "$DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL"
```

`down` does not delete `dungeonmind_world_authority_data`. Destroying the
volume is `docker volume rm dungeonmind_world_authority_data` and is
destructive.

## Backup / clean restore

Store backups outside Git:

```bash
uv run python scripts/eldyrwild_world_authority_recovery.py backup \
  --database-url "$DUNGEONMIND_WORLD_GRAPH_AUTHORITY_DATABASE_URL" \
  --output-path "$HOME/backups/eldyrwild-world-authority.dump"
```

To prove recoverability, restore that file into a second empty authority
database/volume. Matching `READY` + exact D_B is required. Persistence
without a second-target restore is not enough.

## Buddy consumer

After DungeonMind `check` prints `status=READY`, point Buddy at the World
DSN above. Keep APP-STATE on `54329`. Do not merge Buddy PR #689 from this
runbook.
