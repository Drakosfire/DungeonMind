# Migrations (PR B)

DungeonMind owns its schema: migrations, schema versioning, repository
contracts, integrity verification, and reconstruction/import tooling. The
deployment layer owns the PostgreSQL service lifecycle (network, volumes,
backups, credentials) — see `Docs/Decisions/ADR-0002`.

Planned for PR B (see `Docs/Roadmaps/ROADMAP.md`):

- migration runner choice (Alembic or equivalent) and versioning scheme;
- `worlds`, `campaigns`, `graph_revisions`, `world_graph_heads`,
  `source_artifacts`, `source_revisions`, `evidence_refs`,
  `graph_contributions`, `identity_decisions`, `retrieval_sessions`,
  `mind_threads`, `semantic_documents`, `embedding_runs`;
- head publication as a transaction with row-level locking (compare-and-swap),
  never "latest row by timestamp";
- `pgvector` extension verification in the health path.

Do not hand-write SQL here before PR B's design lands.
