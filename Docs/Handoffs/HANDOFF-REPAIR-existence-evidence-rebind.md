# HANDOFF — REPAIR: governed existence-evidence rebind

Created: 2026-10-08.
Status: AUTHORITY REVIEW — CODE-PREPARATION AUTHORIZED AFTER LANDING; DATA EXECUTION HOLD.
Owner: DungeonMind reviewed contribution/publication boundary. Designing steward: PRIME; document author: ARCHITECTURE. ROOT independently reviews this authority PR.
Authority base: `870e879ac8226ae34b064d6846dc018b39db06aa`, tree `2da54275084bff0830f9d251d887dd95a0d6e989`.
Topology: serial — this one-file design PR, then one explicitly dispatched implementation PR. Authority review/merge, fresh main anchor and path ownership precede source implementation. No data operation follows from either merge.

## 1. Mission and observed boundary

Deliver one narrowly typed, append-only correction of existence evidence bindings through the existing reviewed contribution, finalization and publication pipeline. Preserve the object existence claim and every historical revision/receipt. Do not describe this as contradiction of a PC's existence.

The preserved isolated World has genesis/S1/S2 and last-good head `rev:43435e3a237b2e1e5836368b61619895`. Its six genesis PC existence bindings use generic domain `other` correctly, but their opaque `source_domain_key` was lifted as `other` rather than the authoritative artifact key `party_registry`. Strict source-chain reads consequently exclude the six PCs. Correcting the initializer for future Worlds does not repair this persisted World.

Observed code is Core `a501784f21aaafb46d7561f46397a3afdc42f125`. At this authority base, `reviewed_world_initialization._lift_evidence` supplies the erroneous key; `review_materialization_v6.apply_corrections` explicitly rejects existence targets with `correction_target_existence`. Additive node/support assertions retain the old existence binding. No accepted existing repair path has been identified.

RAKE's typed diagnosis is in a private proof packet. The proof must pin the exact six object/assertion IDs, original initialization/contribution/receipt identities, parent payload and authoritative source records before implementation witnesses or any later data recipe. This public handoff contains no corpus prose, credentials or copied private receipts.

Read `AGENTS.md`, `Docs/Architecture/AUTHORITY.md`, the contribution/review contracts and existing V6 materialization/publication code before implementation. Current immutable graph revisions and current durable source state jointly determine admissibility; neither caller testimony nor cached metadata replaces that authority.

## 2. Merge-ready invariant

A finalized, exact-parent reviewed correction may replace only the evidence support of one to six existing native PlayerCharacter existence assertions whose opaque key disagrees with the verified source artifact. One new child and its existing publication receipt record the correction. Object IDs/kinds/labels, all other assertions and historical source/graph/review records remain unchanged. The current child admits the corrected PCs through ordinary strict projection; historical pins retain their original evidence and truthful diagnostics.

Unknown source identity, different artifact/revision/domain, stale parent/preimage, a same-ID changed evidence record, field changes beyond this binding, adopted-era targets, existence retraction or missing verification fail before publication effects.

## 3. Typed contract: one evidence-only variant

Introduce a separate versioned correction item, proposed schema `dm_existence_evidence_rebind_v1`, correction discriminator `rebinds_existence_evidence`, in the existing V2 reviewed correction sequence. Do not add default fields to legacy correction items or globally change serialization. Legacy `contradicts` and `contradicts_and_replaces` remain unchanged; existence targets continue to reject those modes.

The new item binds:

- Native World and exact expected parent revision/payload digest through the existing finalized review/publication plan.
- Original contribution and existence assertion IDs, object ID, full original existence metadata digest and the complete ordered old evidence-reference preimages/digests.
- Accepted replacement assertion ID, explicit old-to-new evidence ID mapping, and authoritative artifact/revision identities and full canonical fingerprints.
- Expected old opaque key and corrected artifact-owned key; generic domain, evidence role, standing/access/openability/locator/span/URI and all other evidence fields remain exact.

Use the existing reviewed node assertion shape for the replacement, with the same object identity/kind and unchanged descriptive payload. Give the replacement a distinct assertion ID and each changed evidence record a distinct ID. Deterministic IDs must bind the reviewed correction/preimages; never overwrite an old evidence record under its old ID. Existing operation/review/finalization/publication identities supply replay and receipt binding; no second persistence framework or table is assumed.

Only this provenance mismatch is admitted: old ref generic domain remains `other`; new opaque key equals the verified artifact's existing `party_registry` key. Do not infer keys from paths, labels, IDs or generic domain, and do not alter artifact/revision classification. Selectors contain one to six unique native PC objects and unique original/replacement assertions. No adopted-era `ka:*` recovery, non-PC/general object repair, label/kind/identity correction, additional assertions or mixed semantic corrections in this contribution.

Current six-ID data is a later exact recipe, not hard-coded production IDs. The bounded type/domain/shape/preimage rule is the reusable capability. Any need to change its semantic boundary returns to PRIME.

## 4. Materialization and owning source proof

Plan from the immutable original parent, before ordinary node merging can hide the original existence assertion. Validate the full batch and replacement assertions before constructing a result. Retain old evidence ledger records; replace only each selected object's active existence metadata/evidence support. New assertion identity and reviewed provenance are explicit, while original canon/epistemic/temporal/access standing and object content remain unchanged except the named evidence-binding correction.

Publication must load and verify the actual authoritative source artifact/revision, including opaque key and canonical fingerprints. A pure helper receiving caller-authored source claims is insufficient. Re-prove source identity coherently inside the owning publication transaction together with expected-head CAS; a source change between prepare and confirm rejects. Reuse existing source repositories and publication transaction machinery. No source SQL update, metadata repair, read-time normalization or admission bypass is permitted.

Prove there is exactly one active existence support per corrected object. A forged or ambiguous target, a missing original contribution/assertion, duplicate ID/mapping, unchanged replacement or simultaneous unrelated effect rejects. Historical initialization receipts must still verify against their original genesis, not be rewritten to point to the child.

## 5. Closed source/test lease after activation

The authority PR changes only this handoff. After its merge, ROOT records the exact implementation base/branch and transfers the following exclusive paths for one implementation PR:

- `src/dungeonmind/contracts/contribution.py` — separate typed correction variant and V2 union; legacy item bytes unchanged.
- `src/dungeonmind/contracts/contribution_review_v2.py` — only if the existing review binding must recognize/preserve the new typed item.
- `src/dungeonmind/application/review_materialization_v6.py` — pure bounded planning/materialization; legacy rejection paths retained.
- `src/dungeonmind/application/review_publication.py` — owning preimage/source proof orchestration.
- `src/dungeonmind/application/repositories.py` — only the narrow publication/source-verification protocol if required.
- `src/dungeonmind/infrastructure/postgres/review_publication.py` — coherent source re-proof under existing publication transaction/CAS.
- `src/dungeonmind/infrastructure/memory/repositories.py` — matching publication behavior for conformance, if required.
- `tests/unit/test_contribution_review_v2.py` — typed validation/review binding and legacy compatibility.
- `tests/conformance/test_review_materialization_v6.py` — exact delta, negative targets and legacy behavior.
- `tests/integration/test_postgres_review_publication_v6.py` — real review/finalization/publication, coherent source re-proof and durable readback.
- This handoff — truthful activation/handback only.

These optional uses are still named paths, not discovery permission. No migration, schema, root config, dependency pin, initializer, vocabulary, retrieval, Buddy or live-data path is leased. A needed unlisted path/storage/public contract is a stop and rebrief. Re-anchor open PRs/leases before dispatch; the current authority snapshot has no open Core PR. RAKE's future initializer fix is separate and must settle or have disjoint source/test ownership before this implementation starts.

## 6. Owning acceptance evidence

1. Synthetic six-PC genesis plus two subsequent revisions reproduce the opaque-key failure through actual stored typed source records and strict projection. No privileged read that suppresses provenance errors counts.
2. Construct an exact reviewed correction with the new variant, finalize it through the existing service and publish via the actual PostgreSQL boundary. Verify one new child/head event/receipt; fresh service and serialized readback verify the correction identities and exact source fingerprints.
3. Compare full parent/child: only selected existence assertion/evidence bindings plus the explicit new evidence records differ. All object IDs/kinds/labels/aliases/summary/properties/aspects, relationships, non-target assertions and old evidence records remain exact. All three historical revisions, genesis/initialization receipts and source/contribution/review history remain immutable.
4. Strict resulting projection admits all six PCs, with ordinary evidence retrieval and anchor/source identity. Unreferenced retained invalid ledger refs must not poison the corrected active view; do not delete or reinterpret them to pass. Historical views retain their truthful old diagnostics.
5. Reuse an actual Buddy native read/mutation-context fixture to verify corrected identity/kind/provenance through the real consumer adapter after Core publication. No provider or operator server. If a Buddy source change is needed, design a separate consumer slice rather than add it here.
6. Source/key/revision/fingerprint drift between prepare and publication, stale head/payload, malformed/missing/duplicate preimages and non-PC/adopted-era targets fail with no child/event/receipt/source mutation. Wrong domain, locator/body/role/access/standing/object-field changes, same-ID changed refs and extra semantic effects also fail.
7. Exact operation retry returns the existing publication receipt without another child; changed operation input conflicts. Existing generic correction semantics, existence retraction rejection and legacy serialized contribution/review/hash behavior remain covered.

Run owning affected checks, lint and cumulative diff inspection. Disposable PostgreSQL fixtures are authorized only after the code lease is activated, with explicit isolated identities; no operator DB clone, provider or runtime operation. Record exact heads/environment/results and exclusions. Helper tests do not substitute for transaction/readback evidence.

## 7. Data execution HOLD and handback

Source approval does not qualify or execute a correction on the preserved three-revision replay target. A later reviewed recipe must pin actual six IDs, source/evidence/preimages, parent head/payload, accepted Core merge/environment, reviewed correction/finalization/publication operation IDs, backup/preservation and strict reader proof. MIND/ROOT must grant its exact isolated data-write lease separately. Never reset/reinitialize the World, rewrite sources/receipts, edit the staged replay pin, skip a cohort row or automatically resume replay after this code merge.

The observed `43435e` head is characterization, not a permanent execution parent. Every data recipe binds the freshly reviewed exact parent while preserving original genesis/S1/S2 preimages. MIND must prove whether the existing suffix writer can proceed before strict six-PC read repair. If it can, replay first and rebind at the reviewed terminal head is allowed under separate leases. If it cannot, rebind first requires an explicit continuation-prefix amendment binding the correction receipt/child before the suffix. No arbitrary moved-head acceptance, stale-parent retry or automatic resumption is authorized. This source capability imposes no ordering beyond the demonstrated writer dependency.

Report authority merge, implementation base/head/PR, changed paths, actual writer tests, strict six-PC readback and all legacy/negative evidence. ROOT independently reviews the authored design PR and implementation. Keep selected-index work, future initializer repair, S28, corpus correction, provider work, live binding/cutover/deletion and operator QA separate. The selected-World hard gate stays in force; corrected six-PC evidence is not full current corpus or semantic completeness.
