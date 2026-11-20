# Governed native source publication: atomic facts and aliases

Status: ACTIVE IMPLEMENTATION. Root final start authorized pinned design0c6198e581ab41b135a21915b6b5f0bcb4274dbd.
Owner: MIND. User explicitly authorizes this lane's design, implementation, review,
PR transport and subsequent separately controlled merge. No ARCH/PRIME gate.
Pinned base: f1dd6d2d4688a44c1428076e00fe32940077237b.
Branch: codex/v10-governed-native-source-publication.
Delivery: one serial Core prerequisite; Buddy manual API remains gated. Profile1
manual enablement remains a separate later Buddy compatibility slice.

## Authority, caller pressure and audit

Read README.md, AGENTS.md, Docs/Architecture/AUTHORITY.md, existing native source
contracts, prospective aliases, extension planner/recovery and memory/Postgres
source repositories. Current code/contracts govern; historical README consumer
rollout summaries are not serving-state proof. Root audit: open143,145-150 concern
classic WorldGraph/adoption;158 owns process/Steward guidance. No planned vNext
regions overlap those active scopes. Do not absorb old PR work or edit standing
Steward/roadmap documents. Root reports no narrower AGENTS under src/tests/Docs.

Buddy protected gate bdab1ab12 supplies memory evidence only: plain governed
extension publishes13 kinds/45 mapping inputs with normal name search, but omits
manual primary-label aliases; separate alias publication preserves aliases with
parent evidence but does not fence current source epoch. This does not exhaust
all alternate ports or show a defect in generic alias publication. Core remains
generic: no Buddy kinds, predicates, UI, caller workflow or profile defaults here.

## Outcome and indivisibility

One explicit source-authorized transaction publishes governed prospective facts,
optional evidence-bearing aliases and, when requested, exact new SUPPORT. The
same transaction validates original source, body commitment, current access,
parent and epoch; persists child/head/event, allocation results, and full receipt.
Splitting contract/planning from the adapters/storage/recovery would expose an
incomplete writer or unrecoverable result, so all form one inseparable PR.

Existing generic alias publisher semantics remain unchanged. Alias targets in
this capability are accepted newly created entities, resolved only by Kernel.
Every accepted new fact/alias's evidence references must belong to this request's
chosen source and exact validated SUPPORT selection. Reject foreign, unrelated,
withdrawn or CONTEXT evidence; no role upgrades. Existing graph rows are preserved,
not reauthorized as newly proposed assertions. Complete disposition inventory
covers all base and alias items; rejected intent remains sealed. No private
allocator/predicted entity IDs/two-stage commit/dummy interval workaround.

## Explicit new public contracts and mode union

Names and signatures below are the implementation contract, not implemented code.
New module: contracts/vnext/native_source_publication.py.

NativeSourcePublicationNewIntervalsV1:
- mode: Literal['new_intervals']
- spans: nonempty bounded list[NativeTextEvidenceSpanRequestV1], unique client_ref
  and byte interval; each evidence_role MUST be SUPPORT. Exact UTF8 boundaries,
  slice hash, source metadata and registration collision checks apply.

NativeSourcePublicationExistingSupportV1:
- mode: Literal['existing_support']
- support: nonempty bounded list[NativeSourcePublicationSupportRefV1]
- each ref seals evidence_ref_id, span_id, full NativeUtf8SpanProofV1,
  introducing_kind ('admission'|'extension'|'publication'), introducing_operation_id,
  introducing_receipt_sha256 and proof_authority_epoch (creation epoch).
- verify exact introducing receipt/proof, original source lineage, parent evidence
  membership, actual SUPPORT role and current access. Client metadata is no authority.
  No new proof IDs/interval registrations or unnecessary source epoch increment.

NativeSourcePublicationEvidenceV1 = Annotated[
    NativeSourcePublicationNewIntervalsV1 | NativeSourcePublicationExistingSupportV1,
    Field(discriminator='mode')
]

NativeSourcePublicationBasisV1 seals schema discriminator, space_id, publication_id,
original_admission_id, source_artifact_id, source_revision_id, expected_body_sha256,
expected_parent_revision_id, expected_source_authority_epoch, timezone-aware
created_at and evidence: NativeSourcePublicationEvidenceV1. All model input is
closed/revalidated; size bounds follow existing native-source maxima.

GovernedNativeSourcePublicationV1 seals the complete basis plus
contribution: ProspectiveKnowledgeContribution,
aliases: list[ProspectiveCreateAliasV1] (may be empty), and
 dispositions: list[ContributionDisposition].
Its discriminator is dm_governed_native_source_publication_v1. Cross-item/alias
identity uniqueness, full governance closure and accepted ResultOf target closure
are enforced. No hidden widening of old V1 parsing.

GovernedNativeSourcePublicationReceiptV1 has discriminator
 dm_governed_native_source_publication_receipt_v1 and seals complete intent SHA,
space/publication/source/original-admission identity and receipt SHA, mode,
source_authority_epoch_before/after, introduced bindings/proofs (new mode only),
verified reused SUPPORT refs (reuse mode only), publication_receipt and public
ProspectiveResultBinding list. Exact final receipt fields/schema are owning code
review surface; no old receipt shape changes. Epoch delta is1 for new,0 for reuse.

## Public API signatures

preview_native_source_publication_evidence(
    *, repository: NativeSourcePublicationRepository,
    request: NativeSourcePublicationBasisV1,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
    audience_labels: Sequence[str] = (),
) -> tuple[EvidenceRefV3, ...]

publish_governed_native_source_publication(
    *, repository: NativeSourcePublicationRepository,
    request: GovernedNativeSourcePublicationV1,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
    audience_labels: Sequence[str] = (),
) -> GovernedNativeSourcePublicationReceiptV1

recover_governed_native_source_publication(
    *, repository: NativeSourcePublicationRepository,
    request: GovernedNativeSourcePublicationV1,
    domain_contract: DomainContractDescriptor,
    semantic_profile: SemanticProfileDescriptorV2 | SemanticProfileDescriptorV3,
) -> GovernedNativeSourcePublicationReceiptV1 | None

Preview is evidence-only, without reservation, writes or guessed IDs. Real public
preview refs may be used to construct the final prospective contribution. Publish
rechecks all source/proof/epoch/parent constraints under repository locks. The
repository port owns publication and typed receipt lookup; it composes existing
revision/source reads. No callback permits a client to substitute authority.

Recovery requires trusted host current owner/World authorization before IO. It
verifies full original intent, original admission/introduction receipts, original
parent lineage/envelopes, complete canonical command SHA (including created_at),
computed child identity/payload/origin, aliases, proofs and allocation mappings.
It does not open today's head, source view/body or perform writes; descendants,
withdrawal and current source unavailability cannot erase verified committed
metadata. It grants no citation/body access. Missing receipt returns None only
when no conflicting publication exists; corruption never falls through to write.
Publisher replay keeps current source authorization, unlike privileged recovery.

## Storage choice and transaction boundary

Approved dedicated table knowledge_native_source_publications, migration0023.
FK original admission and generic publication receipt; immutable JSON receipt plus
fingerprint and indexed source/operation identity. Preserve old0018 table and
extension semantics/readers. No migration of old rows or history rewriting.
Postgres locks global source epoch BEFORE per-space CAS, as current extension
publisher. Memory uses its owning lock and complete rollback snapshot.
New mode adds only newly introduced proofs to source-view/interval/identity indexes;
reuse mode adds none. Proof lookup and interval collision logic must also recognize
new-mode publication introductions, with correct creation epoch. Recovery verifies
both introduction kinds plus prior publications without opening mutable authority.

A narrow private admitted_evidence=() parameter may compose the existing alias
planner with already validated new SUPPORT. Default preserves old behavior. This
parameter is not authorization: new planner independently enforces full selected-
source evidence closure. Any extraction from extension code must preserve old
publication/recovery behavior and accepted validation cost (no new whole-history
verification on ordinary publication; strict immutable recovery remains strict).

## Exact19-path write lease and review map

1. Docs/Plans/HANDOFF-MIND-governed-native-source-publication.md (this handoff)
2. Docs/Contracts/vnext/dm_governed_native_source_publication_v1.json (new standalone schema)
3. src/dungeonmind/contracts/vnext/native_source_publication.py (new wire contracts)
4. src/dungeonmind/contracts/vnext/__init__.py (additive exports only)
5. src/dungeonmind/application/vnext/native_source_publication.py (new planner/APIs/recovery)
6. src/dungeonmind/application/vnext/prospective_aliases.py (narrow admitted-evidence seam)
7. src/dungeonmind/application/vnext/native_source_extension.py (narrow shared proof helper)
8. src/dungeonmind/application/vnext/ports.py (new owning port)
9. src/dungeonmind/application/vnext/__init__.py (additive APIs)
10. src/dungeonmind/infrastructure/memory/vnext_sources.py (atomic state/source view)
11. src/dungeonmind/infrastructure/postgres/vnext_sources.py (transaction/storage/source view)
12. migrations/versions/0023_governed_native_source_publications.py (new table)
13. tests/unit/test_vnext_native_source_publication.py (new owning memory suite)
14. tests/integration/test_postgres_vnext_native_source_publication.py (new owning SQL suite)
15. tests/unit/test_vnext_native_source_evidence_extension.py (old regression)
16. tests/unit/test_vnext_prospective_aliases.py (old regression)
17. tests/integration/test_postgres_vnext_native_source_evidence_extension.py (interoperability)
18. tests/unit/test_vnext_contract_bundle.py (frozen inventory/schema assertion)
19. tests/integration/test_migrations.py (root-approved exact new head expectations)

Root rebrief: migration0023 makes the two existing0022 head expectations stale;
19th path is coupled migration correctness, no unrelated test repairs.

No other paths without root checkpoint. In particular no original bundle or
PUBLIC_CONTRACT_MODELS changes: baseline17 models (actual pinned inventory; earlier18 count corrected), generations, schemas, parsed
model/builder/artifact formats stay unchanged. Standalone schema embeds new public
request/receipt definitions as needed. No old contract regeneration. No shared
Steward/roadmap edits, new env/dependency/domain/pin/UI/transport changes.

## Required proof matrix

- Both modes through actual memory and Postgres writers: one child/event/receipt,
  exact facts/aliases/result bindings, exact citations and authorized search/read.
- Empty aliases and full/rejected alias governance; rejected intent hash/conflicts;
  alias target must be accepted new entity; malformed/mutable inputs refused.
- Foreign/unrelated/CONTEXT/withdrawn refs and wrong source/body/admission/proof,
  role/range/hash/creation epoch/introducing receipt, descriptor mismatch refused.
- Unicode/nonBMP/CRLF intervals and exact body; registration collision no dummy span;
  reuse makes no source identity or epoch change; new increments exactly once.
- Actual competing writer and withdrawal race before owning lock: stale parent/
  epoch or source denial, no child/event/receipt/source/identity/result residue.
- Real fault hooks at child/receipt/proof persistence; complete transaction rollback;
  lost acknowledgement exact retry and recovery without duplicate commits.
- Changed intent/same ID incl differing timestamps with same computed child ID;
  receipt/result/alias/parent/child/root/lineage tampering, missing references closed.
- Metadata recovery after descendants/withdrawal with head/source/body/write
  tripwires; absent returns no mutation; alias/mapping tamper never unchecked return.
- Old generic alias behavior, old extension publish/preview/recovery, source views
  across old/new introductions; frozen bundle/schema/export compatibility.
- Migration upgrade on fixture DBs; populated downgrade refusal; no old data changes.
- Owning focused suites first; appropriate full Core/integration/type/lint/bundle
  qualification with exact-head evidence and all failures preserved. No benchmark
  baseline reruns or claims of serving/performance parity from these tests.

## Resources, stops and continuation

Before allocation actual executor verified Projects UUID
48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8 and task parent/checkout writability. No new
allocation for this design checkpoint. Reuse existing task Core runtime and task
TMPDIR/UV_CACHE_DIR; no new env/resync/worktree/deletion. Future evidence under
scratch/v10-core/governed-native-source-publication after writable check. Only
fixture-owned disposable test DBs; no live/provider/serving/baseline mutations.

Root approved design/storage/lease and explicitly authorized full implementation. Report public API/port/storage scope
growth before editing outside lease. No partial Buddy manual API, profile transition
or source admission bridge. Root owns subsequent Buddy adoption/manual work and
profile1 enablement separately; full V10/current deployment/rollback/V11 remain open.

Retain this unique handoff commit/branch. MIND owns retained task checkout/cache and
all existing gate scratch; no cleanup performed or authorized. Cleanup follow-up
requires explicit scope plus active-process/mount/dirty/unique-data checks.

## Root-approved preparation API rebrief

Public source access gives proof+epoch but not introduction operation/receipt SHA.
Add within the same19 paths:
get_native_source_publication_support(*, repository: NativeSourcePublicationRepository,
 space_id: str, source_revision_id: str, span_id: str)
 -> NativeSourcePublicationSupportRefV1 | None.
This is privileged immutable metadata; trusted host authorizes World ownership
before IO. No body/head/current source opens/writes and no citation authority.
Repository method has the same exact coordinate arguments. Memory uses direct
admission/extension/publication span indexes; Postgres uses the admission span PK
and additive exact-proof GIN indexes in0023 on old extension/new publication JSON.
An index adds no old row/schema-contract semantics. All3 origins verified after
reopen without caller remembering old receipts; context/reuse-only introductions
never masquerade as SUPPORT. Preview/publication still revalidate selected source,
proofs, bytes, parent and current epoch. No new path or second outcome.

## Root create-only boundary clarification

This composition authorizes creation, not destructive governance of other source
facts. Explicitly refuse accepted RetractAssertion, SupersedeAssertion and
ProposeIdentityDecision before repository mutation; rejected inputs may remain
sealed in full intent. Old generic planners retain their behavior. Child-survivor
evidence closure alone cannot authorize deletions; both modes require memory/SQL
zero-mutation tests with pre-existing facts from another source.

## Working implementation checkpoint (not qualification acceptance)

Working diagnostics under scratch/v10-core/governed-native-source-publication:
unit1/2 passed12; expanded unit3 exposed missing test imports, unit5 exposed public
DTO fixture assumptions and the corrected baseline17 count; all raw failures kept.
unit9 owning+old alias/extension/bundle controls passed142. Types4 reports0 errors,
full Ruff3 passes. SQL1 passed14; SQL2 passed43; SQL3 passed51 including migrations;
SQL4 passed90 with1 stale old-extension downgrade-head expectation, corrected only
0022->0023 in the already leased regression file. Each unique32903 test database
has a lifecycle receipt proving zero connections before drop. These are working-
source diagnostics, not final exact-head or broad qualification claims.

Root/Hubble readiness repairs included: create-only accepted items (destructive
retract/supersede/identity refused); selected SUPPORT's own current access and
original role/metadata; exact immutable root/introduction row identities and
original command/child/payload commitments against valid-row substitution. Public
metadata SUPPORT discovery covers admission/extension/new-publication origins;
reuse receipts introduce nothing. Old generic alias semantics unchanged. New
allocation mappings are part of the new atomic receipt, not a second result write.

Integrate accepted origin/main b6539db99fe5c961123bf7615c9d67cd4e40676b before final
exact-head checks: concurrent provenance-batch capability is disjoint and must be
preserved. Original design base f1dd remains historical design anchor. No Buddy
environment sync or live change. Source/receipt provenance manifest and final
owning SQL/unit/type/lint results still required before freeze/review handback.
