# Typed evidence governed review V3

Disposition: `IMPLEMENTED_AWAITING_PRIME_REVIEW`. Base: DungeonMind `aa344e743c138ca099c023d2c384fee90328d37e` (#116). This is a nonlive Core prerequisite for Buddy Graph Review source-readable publication; it does not publish or repair any retained world.

`GraphContributionV3` / `ContributionReviewStateV3` carry `EvidenceRefV2` without altering V1/V2 wire records. The governed review digest binds the complete typed evidence; V6 child materialization preserves `evidence_ref_id`, `source_span_ref_id`, `locator`, and `uri` independently. The PostgreSQL evidence extraction table explicitly reconstructs V1 or V2 by schema version and retains atomic same-ID fingerprint reconciliation. The existing table requires non-null `source_domain`; unclassified typed evidence fails closed rather than being coerced or triggering a migration.

Disposable proof at this branch:

- V3 contract round-trip/digest, source/scope rejection, conflicting same-ID rejection, and materialized child evidence: `tests/unit/test_contribution_review_v3_contract.py` and `tests/unit/test_contribution_review_v3.py`.
- PostgreSQL V3 finalization, fresh-adapter reopen, accepted child publication, typed evidence extraction, exact replay, same-operation conflict, same-ID different-span rollback, stale-parent rejection, and wrong registered campaign scope with no publication mutation: `tests/integration/test_postgres_review_publication_v3.py`.
- Focused V3 plus existing V2/V6/schema-lock cohort: **58 passed** against disposable loopback PostgreSQL with pgvector. No provider calls, corpus export, retained database, migration, or live service action occurred.

Review hold: independent PRIME review and merge remain separate. After reviewed Core merge, Buddy must pin the exact merged Core SHA before its source-readable consumer reactivates. First-World initialization and broad vNext work remain outside this slice.
