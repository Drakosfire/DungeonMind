# ADR-0003 — pgvector as a derived, disposable retrieval index

**Status:** Accepted (founding, PR A)
**Date:** 2026-07-29
**Related:** ADR-0001, `contracts/semantic.py`, `domain/fusion.py`

## Question

What is pgvector's role in DungeonMind's architecture, and what guarantees
apply to embedding data?

## Decision

pgvector is a **semantic candidate-retrieval layer and nothing more**. It is
not the graph, not a canon reducer, not an evidence system, not a truth
plane. Enforced rules:

1. **Authority hierarchy is structural.** The World Graph (immutable
   revisions + head) and source artifacts/admitted evidence are authoritative
   knowledge. Vectors are disposable indexes derived from them. A similarity
   score is never surfaced as factual support; retrieval results carry exact
   source/object identities, and claims cite evidence, not scores.
2. **Required retrieval sequence** (also in `ARCHITECTURE.md` §6):
   exact ID/selection → alias/lexical → vector candidates → deterministic
   fusion → exact graph resolution/traversal → scope+visibility filtering →
   evidence admission → context assembly.
3. **Derived-data rule.** Embeddings are fully rebuildable from durable
   source and graph records. Deleting every vector must not damage graph
   correctness. `EmbeddingRun` provenance (`materialization_run_id`, model
   identity + revision, dimensions, recipe, corpus fingerprint) is recorded
   with every document; re-embedding creates a new run and never silently
   overwrites provenance. The embedding model is never part of graph
   identity.
4. **SemanticDocument v1** (`semantic_document_v1`) carries the charter
   §8.1 field set; initial `document_kind` is limited to `source_chunk` and
   `graph_object`. Assertion embeddings are a later, explicitly-gated
   experiment.
5. **Fusion is deterministic.** Two implemented strategies:
   `reciprocal_rank_fusion` (score-free, chosen default) and
   `weighted_minmax_fusion` (preserved verbatim — including its degenerate
   single-element-channel normalization — as the RulesLawyer parity baseline
   for PR C/D comparison; not adopted as production scoring).
6. **Index strategy.** Exact pgvector search while the corpus is small.
   HNSW/IVFFlat only after exact-search quality, corpus size, filtered-query
   behavior, latency, and build/memory measurements exist — introduced as a
   measured optimization with a recall comparison, never as a setup default.
7. **Hybrid retrieval** in the first PostgreSQL adapter: PostgreSQL full-text
   + pgvector + exact alias/name matching + deterministic fusion + metadata
   filters + bounded results + per-channel diagnostics.

## Consequences

- Disaster recovery posture: losing the `semantic_documents` vector column
  is a re-materialization job, not data loss.
- Model changes are additive experiments (new runs), never mutations; PR D's
  bakeoff compares runs on one corpus fingerprint.
- PR C's benchmark can compare DungeonMind's pgvector retriever against
  RulesIngestion baselines because the fusion baseline is preserved exactly.

## Rejected alternatives

- **Vector score as ranking authority for answers** (plain RAG posture):
  violates invariant "source artifacts and admitted evidence remain the basis
  for factual support".
- **Embeddings inside graph revision payloads**: would couple derived data
  to content addressing and bloat immutable payloads; rejected.
- **Default HNSW at bootstrap**: unmeasured approximation; charter §8.4
  forbids.

## Reversal path

None needed for the core rule (it is a non-coupling). Individual index or
fusion choices are configuration + new embedding runs; both are reversible
by construction.
