# ADR-0028: Atomic native text-source and evidence admission

**Status:** Accepted design and implementation
**Date:** 2026-09-28
**Authority:** PRIME design pass `86e8f22d007df99de577cb412301c5a6d4e2d597` on the settled PR #84 base

**Implementation acceptance:** [PR #85](https://github.com/Drakosfire/DungeonMind/pull/85), reviewed head `0803faf9f84b44148291c68c8dd115f73c68d464`, PRIME Cycle 2 PASS `5334796956`, merged as `7c69e447f6d4acc963ac09c6fb9cb48cc1c5b9cc`. [PR #86](https://github.com/Drakosfire/DungeonMind/pull/86) settled the handoffs and evidence after acceptance. Product adoption and the limits below remain separate obligations.

## Context

An empty native `KnowledgeSpace` can now be initialized, and Keeper accepts
evidence only when it is already present in the exact parent revision. Existing
source adapters do not atomically preserve bounded body bytes and typed span
proofs with that evidence membership. Publishing source metadata separately
would permit a child to cite missing or partial source state.

## Decision

Add a separate, versioned V1 operation that admits one immutable UTF-8
plain-text/Markdown body (at most 1 MiB) and 1–64 explicit byte spans. The
operation allocates deterministic IDs from the complete
`(space_id, admission_id, identity_kind, client_ref)` tuple, creates one
`SourceArtifactV3`, one `SourceRevisionV2`, typed span proofs and corresponding
`EvidenceRefV3` values, then adds only those evidence values to the exact native
child. No entity, assertion, alias, semantic extraction, source lifecycle or
existing contract interpretation is added.

The normal publication receipt and native-source companion receipt, body bytes,
span proofs, child revision, head/event and repository-wide source epoch commit
or roll back together. Exact `(space_id, admission_id)` replay returns the
original receipt, including after descendants; different intent is an
idempotency conflict. PostgreSQL serializes source admission by locking the
singleton source epoch before locking the space. Existing publication paths
retain their current behavior.

The source view pins one epoch in O(1), then loads only requested IDs from the
exact space. A read reveals body text only through evidence membership in the
caller-supplied exact child and only after metadata declarations, visibility,
active status, artifact/revision linkage, whole-body digest and span digest are
verified. Missing, foreign, hidden or undeclared evidence has one non-disclosing
unavailable shape. Corrupt persisted state raises a safe integrity error.

The additive machine-readable companion contract is
`Docs/Contracts/vnext/dm_native_source_admission_v1.json`. Historical
`KnowledgeContribution`, `SourceArtifactV3`, `SourceRevisionV2`,
`EvidenceRefV3`, the frozen V0 bundle and legacy World/source storage retain their
bytes and semantics.

## Consequences and limits

- This capability proves immutable admitted source/evidence availability in a
  native parent; it does not accept the source's claims as graph truth.
- Buddy remains authoritative for the selected saved-document revision and
  must later prove that its submitted bytes match that revision.
- This does not prove source-policy freshness across Keeper prepare/commit,
  mutable source lifecycle, Buddy product adoption, ordinary Agent citation
  routing, DEMO/J3 acceptance, or V7 bridge migration.
- A later governed Keeper publication is a distinct child. If it fails, the
  admitted source/evidence child remains durable and can be deliberately reused.
- PostgreSQL downgrade must refuse to discard populated native source records.

## Acceptance evidence

The implementation PR must prove public initialization → public admission →
exact child membership; exact byte/span behavior; zero-mutation rollback at each
transaction stage; replay, response-loss recovery and concurrency; epoch-pinned
old/new views; privacy and integrity failures; PostgreSQL upgrade/rollback/read
after fresh connections; unchanged frozen contracts and regressions; and a real
WorldKeeper prepare/commit witness using the exact approved Keeper pin without
seeded evidence. These proofs are recorded in
[the implementation evidence report](../Reports/REPORT-NATIVE-text-source-evidence-admission.md)
and the accepted PR #85: exact-head core CI passed 2,046 tests (3 skipped),
PostgreSQL integration passed 308 tests (1 skipped), and the real WorldKeeper
consumer witness passed at pin `49a8620f066ce7ef8972a699020c012f50af9158`.
