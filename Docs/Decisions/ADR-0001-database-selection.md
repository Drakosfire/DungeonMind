# ADR-0001 — Primary datastore: PostgreSQL + JSONB + pgvector

**Status:** Accepted (founding, PR A)
**Date:** 2026-07-29
**Deciders:** founding agent, per operator charter
**Supersedes:** none
**Related:** ADR-0002 (lifecycle ownership), ADR-0003 (pgvector role)

## Question

Which datastore family does DungeonMind use as its primary substrate for the
World Graph, contributions, evidence, retrieval sessions, and semantic
documents?

## Context

Closed invariants (see `Docs/Architecture/ARCHITECTURE.md` §3) require:
immutable content-addressed revisions, atomic head advancement with
stale-parent rejection, exact revision reads, scope/visibility filtering on
every read, filtered semantic retrieval over
world/campaign/revision/visibility metadata, and rebuildable derived indexes.

## Comparison (charter §5.4 — comparison performed, not assumed)

### Option 1 — PostgreSQL + JSONB + pgvector (selected)

- **Transactions & CAS:** native; head publication via row-level lock
  (`SELECT ... FOR UPDATE` on `world_graph_heads`) inside one transaction.
- **Relational constraints:** FK ownership chains (world → campaign →
  revisions, contributions, documents) enforced by the database.
- **JSONB flexibility:** canonical graph snapshots stored whole in v1; no
  premature normalization of nodes/edges/assertions. Typed columns for
  identity/lifecycle; JSONB for payloads.
- **Recursive graph queries:** available (recursive CTEs) if normalized query
  tables are later justified by benchmarks.
- **Full-text search:** native (`tsvector`/`tsquery`), co-located with
  metadata filters — enables one-query hybrid lexical+semantic retrieval.
- **Vector retrieval:** pgvector in the same engine, filtered by relational
  predicates; one operational and backup boundary for graph and vectors.
- **Cost:** one new service in the topology; migration tooling (Alembic)
  becomes part of this repo.

### Option 2 — MongoDB + application-managed integrity/vector (rejected)

- Matches RulesLawyer's current home, but: no multi-document transaction
  discipline comparable to row-lock CAS for head advancement (Mongo
  transactions exist but the team's operational pattern is single-document);
  graph integrity constraints move into application code; vector search
  requires Atlas Search (external managed service) or a separate engine,
  splitting the operational boundary. The founding handoff explicitly forbids
  treating "Mongo already exists" as a reason, and forbids making Mongo
  disappear merely for consistency — RulesLawyer keeps Mongo; DungeonMind
  does not adopt it.

### Option 3 — Firestore + external vector system (rejected)

- `statblocks_v1` proves the repository-port discipline on Firestore, but
  Firestore lacks: transactional CAS across an insert+pointer-update pair with
  stale-parent rejection semantics at the database level, full-text search,
  recursive queries, and vectors. An external vector system (e.g., a hosted
  index) adds a second failure/backup/consistency boundary for data that must
  be filtered jointly with graph metadata. Rejected on boundary-splitting
  grounds, not on Firestore capability for its existing use cases.

## Decision

PostgreSQL + JSONB + pgvector is DungeonMind's primary substrate.

Hybrid relational/document v1: relational identity and lifecycle columns;
canonical graph snapshots and typed records as JSONB. Minimum schema families
(charter §7.2): `worlds`, `campaigns`, `graph_revisions`,
`world_graph_heads`, `source_artifacts`, `source_revisions`, `evidence_refs`,
`graph_contributions`, `identity_decisions`, `retrieval_sessions`,
`mind_threads`, `semantic_documents`, `embedding_runs`.

## Consequences

- PR B adds `migrations/` (Alembic), `infrastructure/postgres/`, and a pinned
  dev/CI pgvector substrate; integration tests become opt-in locally,
  required in CI.
- Heavy dependencies (`psycopg`, `pgvector`, `alembic`) stay behind the
  `postgres` extra; core importability is unaffected.
- Normalized head/query tables are deferred until benchmarks demonstrate
  need (charter §7.4).
- Source bodies may live in object storage; identity, hashes, revision
  metadata, locators, and evidence anchors stay durable in PostgreSQL.

## Rejected alternatives

- MongoDB + app-managed integrity/vector (above).
- Firestore + external vector system (above).
- "Reuse the existing LibreChat PostgreSQL instance directly" — rejected as
  an ownership decision; see ADR-0002.

## Reversal path

Repository ports (`application/repositories.py`) are the seam. A different
primary store is a new infrastructure adapter + migration of durable records;
contracts and domain logic do not change. Reversal is expensive (data
migration) but not architectural.
