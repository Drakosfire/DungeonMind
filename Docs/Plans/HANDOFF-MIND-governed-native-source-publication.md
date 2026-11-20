# Governed native source publication: atomic facts and aliases

Status: ACTIVE FINAL QUALIFICATION, CorePR239; root owns review/merge.
Owner: MIND, explicit full-lane authority; no ARCH/PRIME gate.
Branch: codex/v10-governed-native-source-publication.
Current comparison/accepted-quality base: ecaaa2da0da1db028e260985cf8abc20ef6dfa9c.
Original design base: f1dd6d2d4688a44c1428076e00fe32940077237b; approved design
0c6198e581ab41b135a21915b6b5f0bcb4274dbd. Original reviewed publication runtime:
ee3eb3f945cc7c91902ec983d15402070f79ac7c, Hubble review5985803881 SOURCEPASS with
qualification HOLD (not final acceptance). Root explicitly released final
integration; no public capability/code expansion is authorized in this phase.

## Fast reentry and serial dependencies

Accepted quality prerequisites are integrated normally, without history rewriting:
- Core240 merge757cc986a55aaba7013e27724e42ef50f814804c, code36c5f1f0538716413ddd4b90000af0ccf41997b7,
  review5985957336, CI44650060111 all3SUCCESS; private optional counter typing,
  annotation/tuple boundary and lint only, owning194passed.
- Core241 mergeecaaa2da0da1db028e260985cf8abc20ef6dfa9c, code671a361c98330df407f99fafeba0f24dd894b78e,
  review5986075059, CI44651370225 all3SUCCESS; test-only import isolation,
  red->green ordered pair, module26/full3207passed,29assertions unchanged.

Root explicitly expands original19-path allowance to21 ONLY to settle these two
owning handoffs. No extra production/test edits. All10 publication runtime/schema/
migration files are byte-identical to reviewedee3: retained
scratch/v10-core/governed-native-source-publication/integration-ecaaa-runtime-equivalence.json.
Migration0023 SHA2560193a186411b6a2dfaba5f4704fe2d1469d4d61fe2368d268c75b1436a1b4fc7
and alembic.ini stay stable during independent Buddy installed-runtime consumer
SQL proof. No changes without root checkpoint; no Buddy/Core overlay or live write.

Final committed integrated-head fullunit/conformance, owning SQL/migration,
Ruff/types/frozenbundle/diff and lifecycle proof are required before final freeze.
Do not repeat the whole12minute SQL cohort locally: root's originalee3 fullSQL
586passed1skipped is historical proof, not a new-head execution. FinalCI repeats it.

## Authority and current scope

README.md, AGENTS.md, Docs/Architecture/AUTHORITY.md govern. Fresh fetched main is
exactecaaa. Current openPR inventory239/158/150-145/143 unchanged:239 owns this
publication scope,158 shared process/Steward guidance is excluded, other stacks
are classic/adoption regions. No old work absorption, lease revocation or closure.
New prerequisite seals are root-authorized docs only; accepted source changes
arrive through main, not extra edits in this capability.

Buddy protected gate bdab1ab12 is memory evidence: plain governed extension
preserves13kinds/45mapping inputs and normal names but omits primary-label aliases;
parent-evidence alias publisher lacks current epoch fence. This does not exhaust
all ports or identify a generic alias publisher defect. No Buddy/domain semantics,
profile default/adoption, UI, transport, live deployment or benchmark changes here.

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

## Exact21-path allowance and review map

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

20. Docs/Plans/HANDOFF-MIND-complete-entity-batch-lint-types.md (accepted240 seal only)
21. Docs/Plans/HANDOFF-MIND-cache-verification-import-isolation.md (accepted241 seal only)

No other paths without root checkpoint. In particular no original bundle or
PUBLIC_CONTRACT_MODELS changes: baseline17 models (verified exact pinned inventory), generations, schemas, parsed
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

## Evidence and limits: do not relabel historical executions

Retained namespace: scratch/v10-core/governed-native-source-publication.
- Original reviewedee3 scoped257unit/read and91SQL/migration passed0skips; lifecycle
  verifies each unique32903DB removed after zero active connections. Exact source/
  command/log hashes in final-ee3eb3f-inputs.json. Original bundle byte-identical.
- Root originalee3 fullunit/conformance3279passed1FAILED (cache0!=1 reproduced on
  exactbase/candidate); fullRuff6/type1FAILED also independently executed on exact
  b653 mirror. Hubble independent142passed; old CI44646724178 corelintFAILED before
  unit/types, integration+WorldKeeper/service types and benchmark-smokePASSED.
- Root originalee3 fullSQL586passed1skipped/exit0, ownedDBremovedzeroactive. That
  prior integration success is preserved, not renamed as current execution.
- Quality parents240/241 resolve those static/import-test defects. New integrated
  full tests must demonstrate closure; no silent waiver or old-result relabeling.
- Initial working failures (missing test imports, public DTO assumptions, baseline
 17-model count correction, SQL4 stale old-extension0022 head expectation) remain
  retained. No frozen old schema/bundle was regenerated. SQL4 failed90/1, not green.

## Resources, stops and next delivery

Verified Projects UUID48fa5d10-fe99-4557-9fc9-d8a2a4b41ac8 plus actual writable task
checkout/scratch. Existing Core runtime cache/v10-core-unit, per-process Core-only
PYTHONPATH=src and task TMPDIR/UV_CACHE_DIR; no tool env sync/newenv/worktree/mirror.
Only unique fixture32903DBs and task-owned conventional generated paths. No
provider/serving/live/sourceauthority/baseline changes. MIND retains all current/
prior logs, manifests, mirrors/cache under active full goal; no filesystem cleanup.
Cleanup follow-up needs approved scope and process/mount/dirty/unique-data checks.

After final committed-head qualification: updatePR239, push/freeze exacthead and
report actual handles/results/limits to root. Independent source/evidence review
and finalCI precede root merge. Buddy consumer currently may diagnose installedee3
with migrations-only checkout; final accepted merge pin is mandatory. Buddy manual
API/UI/current-route retirement/explicit World transition/deployment/rollback/V11
remain separate open full-goal work; this capability is not their completion.
