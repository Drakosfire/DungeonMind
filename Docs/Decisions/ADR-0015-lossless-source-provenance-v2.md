# ADR-0015 — Lossless source provenance v2

**Status:** Accepted  
**Date:** 2026-08-07  
**Deciders:** implementing agent, per operator dispatch  
(`source/whole-world-provenance-v2`)  
**Supersedes:** none  
**Related:** ADR-0001 (datastore), ADR-0002 (lifecycle ownership), ADR-0014
(assertion-scoped graph v4), `contracts/evidence.py`,
`application/graph_snapshot_v5.py`, `application/graph_scope.py`

## Question

How does DungeonMind represent whole-world source provenance without overloading
v1 axes, silently defaulting unknown producer values, or conflating document
standing with access policy?

## Context

v1 `SourceArtifact` required `source_domain` and `visibility` and used a
single string `authority` vocabulary. Producers such as DungeonMindBuddy carry
axes v1 cannot express separately: opaque producer classification, document
review standing, producer visibility classification, workspace document linkage,
and JSON lineage. v1 also cannot represent “unknown access policy” without
fabricating a default.

Graph v4 fixed assertion-scoped knowledge state but still carried v1 evidence
rows whose `source_domain` overloads producer and kernel semantics.

## Decision

1. **v1 source/evidence contracts and graph schemas v1–v4 are immutable.**
   `dm_source_artifact_v1`, `dm_evidence_ref_v1`, `dm_source_revision_v1`, and
   `dm_union_graph_v1`–`v4` bytes and semantics are unchanged. v2 introduces
   `dm_source_artifact_v2`, `dm_evidence_ref_v2`, and
   `dm_workspace_document_ref_v1` only.
2. **`dm_union_graph_v5` exists because evidence v2 cannot be retrofitted into
   v4.** V4's evidence ledger is historical and v1-shaped. V5 is v4 assertion
   grain plus a v2-only evidence ledger — no other World Graph redesign.
3. **`source_domain_key` is opaque producer classification.**
   `source_domain` is an optional generic DungeonMind provenance family. The
   kernel never infers one from the other and never interprets producer keys.
4. **`review_state`, `authority`, and graph assertion `canon_state` are
   independent axes.** Document standing, evidentiary role, and graph canon are
   never coerced into each other. Buddy `authority_state` is not
   `SourceAuthority`.
5. **`source_visibility_state` is producer classification only.**
   `visibility` is DungeonMind access policy. Producer classification never
   grants access.
6. **Unknown producer values are required-but-nullable.** There are no silent v1
   migration defaults for `authority` or `visibility`.
7. **`visibility is None` fails closed.** Provenance resolution returns
   `EvidenceScopeVerdict.SCOPE_UNKNOWN`; `source_visibility_state` must not
   substitute.
8. **`workspace_document_ref` is distinct from `source_artifact_id`.** Neither
   field is derived from the other; workspace identity is foreign provenance.
9. **`lineage` must be JSON-compatible.** Non-JSON values fail closed at
   contract validation. Empty lineage is valid; lineage is audit metadata, not
   graph truth.
10. **Evidence locator forms remain independent.** `source_span_ref_id`,
    `locator`, `uri`, `source_locator`, and `line_ref` are not merged or given
    precedence.
11. **Evidence `session_id` is real-world session association, not fictional
    time.** No derivation into `temporal_scope` or assertion `session_refs`.
12. **Content hashes remain on `SourceRevision` only.** No
    `content_sha256` on `SourceArtifactV2`. `updated_at` never selects the
    current revision.
13. **One `SourceRepository` reconstructs by `schema_version`.** No parallel
    `SourceRepositoryV2` port. Idempotency conflict on same id + different
    fingerprint is unchanged.
14. **PostgreSQL stores full payload in jsonb; migration 0004 only drops NOT
    NULL on `source_domain` and `visibility`.** Column values on put reflect
    the model (`None` when unknown). v1 rows are not rewritten.
15. **Evidence schema pairing is strict.** v4 rejects v2 evidence; v5 rejects
    v1 evidence. v2 evidence resolving against a v1 artifact (or the reverse)
    is a provenance mismatch.
16. **No Buddy or game-system imports enter the kernel.** Public graph dumps
    exclude v2-only provenance fields (`workspace_document_ref`, `review_state`,
    `lineage`, `source_span_ref_id`, etc.).

## Consequences

- Whole-world imports can persist lossless producer metadata without lying about
  unknown access policy.
- Graph v5 can cite v2 evidence while keeping v4 assertion admission semantics.
- Callers must supply v2 artifacts when using v5 evidence rows; mixed-schema
  chains fail closed rather than coerce.
