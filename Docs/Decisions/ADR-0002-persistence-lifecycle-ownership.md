# ADR-0002 — Persistence lifecycle ownership (IaC split)

**Status:** Accepted (founding, PR A)
**Date:** 2026-07-29
**Related:** ADR-0001 (datastore), `Docs/Reports/RECON-2026-07-29-founding-inventory.md` §D

## Question

Which repository owns (a) DungeonMind's schema/migrations and (b) the
PostgreSQL service lifecycle (network, volumes, backups, secrets)?

## Evidence inspected

- `DungeonOverMind/docker-compose.prod.yml`, `docker-compose.dev.yml`,
  `docker-compose.local.yml`, root `Dockerfile`, `Caddyfile`, `Makefile`.
- DungeonMindServer `Dockerfile`, `pyproject.toml`, `dependencies.py`,
  `.env.example`, `routers/ruleslawyer_router.py`, `routers/health.py`,
  `statblocks_v1/infrastructure/{firestore_repositories,runtime}.py`.
- LibreChat `docker-compose.yaml` (vendored under `Sizzek/DungeonMindOvermind/
  LibreChat/LibreChat-Docker/`) and `Sizzek/LibreChat/docker-compose.yaml`.

Key findings (recon report §D for full citations):

- `DungeonOverMind` root owns production composition: root Dockerfile builds
  DungeonMindServer; Caddy terminates TLS; dev/local compose stacks run
  MongoDB + Redis + mailhog for DungeonMindServer. It is the deployment
  orchestrator in practice, despite the workspace directory name.
- The only pgvector material anywhere is LibreChat's vendored compose:
  `pgvector/pgvector:pg16` (~PostgreSQL 16, `librechat` DB). It is
  **unverified** — not proven running, backed up, reachable, or appropriate;
  its credentials are generic example values and its lifecycle is owned by
  LibreChat's stack, not by DungeonMind consumers.
- DungeonMindServer is a compute backend: stateless container behind Caddy;
  state lives in MongoDB/Redis/Firestore/R2. It does **not** own shared data
  infrastructure today.

## Decision

Per the charter's ownership heuristic (§5.3), confirmed by evidence:

| Concern | Owner |
| --- | --- |
| Schema migrations, schema versioning, database contracts, repository ports, PostgreSQL adapters, integrity verification, reconstruction/import tooling, semantic-document materialization, embedding-run provenance | **DungeonMind** |
| Dev/CI PostgreSQL substrate definition (pinned pgvector image, compose) | **DungeonMind** (PR B) |
| **Production** PostgreSQL service lifecycle: starting the service, enabling pgvector, networks, volumes, backups, credentials, resource limits, recovery | **Deployment orchestrator — DungeonOverMind** (PR F) |
| DungeonMindServer | consumer configuration + its own RulesLawyer adapter only (PR E) |
| RulesIngestion | benchmark methodology; external benchmark client (PR C) |

Dedicated database and role: production PostgreSQL gets a `dungeonmind`
database with a dedicated least-privilege role, wired by the orchestrator;
generic LibreChat/example credentials are never reused (charter §14).

## Rejected alternatives

1. **DungeonMindServer as PostgreSQL lifecycle owner.** Rejected: it does not
   own shared data infrastructure today (evidence above); putting lifecycle
   there "because it's an existing backend" is exactly the failure mode the
   charter §5.3 warns against. It remains a consumer host.
2. **Reusing the LibreChat pgvector instance for DungeonMind.** Rejected:
   ownership by an unrelated service (stop condition §15.4 territory),
   generic credentials, unverified operational posture, and an unacceptable
   coupling of DungeonMind's backup/recovery to LibreChat's lifecycle.
3. **A brand-new dedicated IaC repository.** Deferred, not rejected:
   DungeonOverMind already composes the production stack; creating a third
   repo now adds coordination cost without new capability. Revisit if
   DungeonOverMind's composition role is itself split.

## Consequences

- This repo gains `migrations/` + dev/CI compose in PR B without claiming
  production lifecycle.
- PR F (deployment/IaC integration) lands in DungeonOverMind: private
  networking, persistent volume, dedicated credentials, backup/restore
  expectations, resource limits, health checks.
- Until PR F, "where PostgreSQL runs" is: dev/CI containers owned by this
  repo's compose; production does not exist yet.

## Reversal path

Ownership moves by moving compose/service definitions and secrets wiring;
schema and migrations stay in DungeonMind regardless. Low reversal cost for
the orchestrator choice; the DungeonMind-owned half is invariant.
