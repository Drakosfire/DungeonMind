# Source-description facet withdrawal

ACTIVE. PRIME solo implementation; ARCHITECTURE review/advice. Base
30c7f64ea52d74bde65dbb46efe3d462042c92e3; branch
codex/source-description-facet-correction. Serial Core slice; no open Core PRs.
Buddy #1243 is merged; DOGFOOD owns separate Buddy UI/source packaging work.

## Outcome
Permit a finalized V3 Graph-review contribution to withdraw an exact published
V3 extraction-node worldbuilding description facet. New correction kind
`contradicts_source_description` requires null replacement and an audited
`diagnostics.source_description_withdrawal_reason` nonblank string. Existing
correction serialization/digests stay unchanged. This withdraws the extracted
interpretation, not the original source or object existence.

Resolve targets through the exact pinned parent's publication ancestry. Verify
revision/publication/review/contribution bindings, accepted extraction node,
current subject identity/kind/scope, exact source artifact/revision and complete
typed supporting evidence. Reject foreign/unpublished/adopted/unsupported,
already suppressed or duplicate targets. An internal non-wire proof binds the
review, parent, and target pairs. Pure materialization requires this proof and
preserves graph object/relationship/evidence bytes; do not add description IDs
to whole-assertion corrected IDs. Retrieval applies the kind only to node
source descriptions, preserving other same-subject observations and history.
Normal finalized-review authorization, parent CAS and publication replay remain.

## Exclusive write set
- This handoff
- src/dungeonmind/contracts/contribution_review_v3.py
- src/dungeonmind/contracts/contribution.py
- src/dungeonmind/application/source_description_correction.py (new)
- src/dungeonmind/application/review_publication.py
- src/dungeonmind/application/review_materialization_v6.py
- src/dungeonmind/application/world_graph_retrieval.py
- tests/conformance/test_source_description_withdrawal.py (new)
- tests/integration/test_postgres_source_description_withdrawal.py (new)

Prove real finalize → publish → fresh retrieval, unchanged graph payload,
historical openable evidence, unrelated observations, descendants and exact
replay. Reject stale/missing proof, duplicate/repeated withdrawals, unsupported
or unresolved targets. Pin existing serialized correction bytes/digests.
No runtime/provider/retained publication/corpus writes. Synthetic in-memory
and newly created disposable PostgreSQL owning boundaries only in this slice. Preserve before/end refs;
complete one PR and independent exact-head review before PRIME merge. Retained
Mirathorn withdrawal requires separate exact-plan review after implementation.

Scope clarification: V3 review intent/record verdict lists may be empty only
for a correction-only description withdrawal; the intent/state must reject
empty ordinary or mixed-kind reviews. This is necessary to avoid fake audit
assertions for a real, confirmed facet withdrawal. V2 contracts are unchanged.

Author evidence: 147 focused tests pass across 23 new withdrawal cases and
existing V2/V3 review, materialization, current-node/worldbuilding observation
retrieval and search suites. New tests use actual capability-checked finalization,
publication, a fresh retrieval service, historical source-anchor resolution,
exact replay, descendants, same-subject observation preservation, failed competing
CAS, incomplete evidence, corrupt ancestry, and missing/stale/forged internal
proofs. Existing correction serialization remains identical. Ruff and cumulative
diff checks pass. No provider or retained/runtime action occurred. The additional PostgreSQL witness passed in a fresh migrated disposable database
and the database was removed. Retained Mirathorn acceptance remains unclaimed.

Persistence gate added: exercise correction-only finalized review storage,
publication, fresh repository/service readback and replay in a freshly created
disposable PostgreSQL database. Never pass a retained DSN to truncating fixtures.
