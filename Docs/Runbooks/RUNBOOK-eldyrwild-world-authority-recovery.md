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
