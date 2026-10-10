# HANDOFF — NATIVE: bind an admitted legacy source to exact UTF-8 span proof

**Created:** 2026-10-09

**Status:** DESIGN READY FOR INDEPENDENT REVIEW; no runtime lease active

**Repository / branch:** `Drakosfire/DungeonMind` / `codex/legacy-native-source-proof-binding`

**Design base:** `8222743ba8c61095f779feff6c969f5b79534590` (PR #106 merge)

**Owner:** DungeonMind source/evidence authority; Buddy supplies the explicit producer mapping; PRIME reviews and sequences implementation
**One-line mission:** Make an existing native evidence reference openable by durably proving exact bytes and an explicit UTF-8 span against its already recorded legacy artifact and revision IDs.

## §1 Decision and present truth

The verified `dungeonmind_cutover_live` state is at Alembic `0014_adopted_withdrawal_v2`. Legacy artifact `corpus:eldyrwild:session-22-recap` and revision `sha256:06c978131f31e6ec85ff6286fe550f07bd2a3c5972c86bf29533079aebbf7083` exist. The producer's file exists and matches that revision digest. The native source admission and span tables each have zero rows. The graph names semantic span `span:session-22:mireward-road` and evidence `evidence:corpus:recap:s22:mireward-road`, but no native byte-interval proof binds that span to the revision. These are incident facts supplied by the verified read-only authority check, not a claim that this handoff inspected private rows.

`NativeTextSourceAdmissionV1` is **not** a direct repair. It allocates new `src:`, `srev:`, `span:` and `ev:` identities and publishes a new evidence-bearing child. Its optional `origin` is an opaque link, not verification of a legacy source pair. A V1 admission could preserve the old IDs as an origin annotation, but the existing graph evidence would still point at the old IDs. A second source revision is unjustified while the exact body SHA is unchanged. Neither a filename, the semantic span ID nor the evidence ID supplies byte positions.

Design an additive, versioned **legacy-to-native proof binding** operation. It verifies the existing legacy artifact/revision and already admitted native evidence, stores an exact native UTF-8 body copy and typed span proof under those same artifact/revision/evidence/span IDs, and advances only native source authority. The legacy rows, native graph revision, head and evidence values remain immutable. The source epoch can change read availability at an exact graph revision; `AUTHORITY.md` §3 already treats source standing as authority separate from graph identity. The operation must not assert new graph truth.

This is a design lease only. Independent review of this document decides whether the post-hoc source-authority binding is accepted. No database, runtime, corpus or graph operation is authorized by this PR.

## §2 Read order and owner boundary

1. `Docs/Architecture/AUTHORITY.md` §§1–5, 8 and `Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md` §6.
2. `Docs/Decisions/ADR-0028-native-text-source-evidence-admission.md`, `Docs/Handoffs/HANDOFF-NATIVE-text-source-evidence-admission.md`, and its accepted implementation report.
3. `src/dungeonmind/contracts/vnext/native_source.py`, `source.py`, `application/vnext/native_source_admission.py`, `native_source_access.py`, `ports.py`, and both native source adapters.
4. `src/dungeonmind/contracts/evidence.py`, `application/source_admission.py`, and migration `0015_source_admission`: the current legacy pair and receipt authority.
5. `Docs/Handoffs/HANDOFF-AHEAD-selected-source-anchor-index.md` for selected-target metadata scope. It cannot manufacture missing source proof.
6. Buddy's current consumer handoff `HANDOFF-HERMES-worldbuilding-source-span-follow-through.md` and PR #731, as consumer evidence only. That lease does not add a producer-side local index.

DungeonMind owns the identity check, body and slice digests, typed proof, admission receipt, source epoch, provenance snapshot, authorization and read resolver. Buddy owns the saved-document/body selection and the explicit mapping from semantic span to byte interval in that exact UTF-8 revision. Core verifies supplied bytes against durable legacy revision metadata; it does not authenticate a separate Buddy database merely from a caller's document ID.

## §3 Proposed companion contract and transaction

Add `dm_native_legacy_source_proof_binding_v1` as a new companion family. Keep `NativeTextSourceAdmissionV1`, `NativeUtf8SpanProofV1`, `SourceArtifactV3`, `SourceRevisionV2`, `EvidenceRefV3`, the frozen bundle and historical receipts byte-for-byte unchanged. A new request contains:

- `space_id`, `binding_id`, exact `expected_head_revision_id`, `legacy_world_id`, aware `created_at`;
- existing `source_artifact_id`, existing `source_revision_id`, exact `expected_body_sha256`, and the complete, nonempty UTF-8 `body_text` (at most 1,048,576 bytes);
- an explicit generic `SourceArtifactV3` policy snapshot or fields sufficient to construct it, with classification, authority, visibility, status and declared source annotation metadata; no defaults for unknown legacy policy axes;
- one to 64 unique bindings, each with existing `evidence_ref_id`, existing opaque `source_span_ref_id`, existing `evidence_role`, explicit half-open `start_byte` / `end_byte`, and `expected_slice_sha256`.

The request is not accepted merely because the IDs and SHA strings match caller input. In one transaction, after locking native source epoch then space, Core must read the exact legacy artifact/revision pair and current native head, verify the legacy world/artifact/revision binding and stored revision SHA, verify submitted bytes and each UTF-8 aligned slice, and inspect each evidence value in the exact native revision. Every evidence value must already bind the supplied artifact, revision, span ID and role and have `can_open_source=true` and `can_highlight_span=true`. Validate source classification, policy, visibility and metadata against the accepted native domain contract and authoritative legacy source state; unknown or irreconcilable policy is a stop, never a permissive default. Preserve the exact legacy IDs in the typed native record and in the receipt. Do not parse or hash an opaque span/evidence ID to invent positions.

The durable companion record stores the exact body bytes with native storage kind `dm_native_utf8_body_v1`, a native `SourceArtifactV3`/`SourceRevisionV2` snapshot under the existing IDs, `NativeUtf8SpanProofV1` values under the existing span/evidence IDs, the exact legacy pair reference, canonical command SHA, record fingerprint, source epoch and an idempotent receipt. The original legacy `SourceRevision` retains its original body-storage/locator fields. The native source view must resolve both accepted V1 admissions and these legacy companion bindings by exact `(space_id, artifact_id, revision_id, span_id)`, including targeted provenance snapshot reads. It must reject cross-family ID collisions or conflicting duplicate bindings before mutation.

One commit makes the body, all proofs, receipt, indexes and incremented source epoch visible together; no new `KnowledgeRevision`, publication receipt, graph event or head movement occurs. Same `(space_id, binding_id)` and byte-identical canonical command replays the original receipt after descendants. Changed body, interval, policy, evidence, parent or legacy pair under that ID is an idempotency conflict. An ambiguous post-commit response recovers by that same ID; corrupt persisted state is an integrity failure, never an unavailable or success result. Old pinned source views do not see the new epoch; fresh contexts see the complete binding. Access still requires exact revision evidence membership, generic visibility and annotation admission, active standing, body digest and slice digest. Hidden, absent and unauthorized data return the existing non-disclosing unavailable shape.

Use an additive table or equivalent versioned native source record. Do not alter migration `0011`, insert synthetic V1 rows, rewrite legacy pair rows, or reinterpret the V1 companion receipt's publication binding. Migration `0015_source_admission` is on current `main`, while the verified live database remains at `0014`; any future runtime deployment must separately clear that schema gate before this new migration can apply. This design PR does not do so.

## §4 Exact acceptance fixture and falsifiers

The implementation fixture must be synthetic and version-pinned. It must carry these exact fields and relationships (the real body and offsets are **not** in this design PR):

```text
space_id / legacy_world_id / exact native revision and expected head
binding_id / created_at / schema_version / canonical command_sha256
legacy source_artifact_id = corpus:eldyrwild:session-22-recap
legacy source_revision_id = sha256:06c978131f31e6ec85ff6286fe550f07bd2a3c5972c86bf29533079aebbf7083
legacy artifact world/status/current_revision_id/classification/authority/visibility
legacy revision content_sha256/body_storage/locator metadata (not body text)
native artifact classification/authority/visibility/domain_metadata snapshot
body byte count / expected_body_sha256 / actual SHA-256 equality
evidence_ref_id = evidence:corpus:recap:s22:mireward-road
source_span_ref_id = span:session-22:mireward-road
evidence role / source artifact ID / source revision ID / can_open_source / can_highlight_span
start_byte / end_byte / expected_slice_sha256 / actual slice SHA-256 equality
receipt binding ID / source epoch / exact legacy pair / source and span/evidence IDs
```

The production producer fills the exact offsets and slice digest from the verified saved revision; the synthetic fixture uses invented bytes with internally consistent digests and the same *shape*. Do not check in private body text or infer offsets from the example IDs. If the real evidence fields or standing differ from these preconditions, stop and return the exact mismatch. In particular, false open/highlight flags or an evidence reference absent from the exact native revision require a separately governed graph child, not a silent sidecar override.

Required owning proof for a later implementation: in-memory and PostgreSQL success/read through the existing evidence ID; byte and slice tampering; UTF-8 boundary, wrong revision, foreign space, policy/visibility and wrong evidence ID failures; no mutation on each preflight or transaction fault; same-ID replay and conflicting replay; concurrent same-ID and distinct-ID races; lost response recovery; old/new epoch views; downgrade refusal when populated; unchanged V1 admission behavior and legacy pair values. A live Session 22 check is a separate, explicitly authorized rollout gate after synthetic acceptance.

## §5 Serial owner sequence and stops

1. PRIME/ARCHITECTURE independently review this design and settle the exact companion semantics. No runtime lease activates from this document alone.
2. DungeonMind implements the additive contract, authority port/adapters, source view and access proof in one bounded PR on a newly pinned current `main`; it tests repository transaction and public read behavior. If legacy/source policy cannot be mapped without invention, return to design before code.
3. Buddy receives that accepted Core merge and publishes an explicit producer mapping for the exact saved S22 revision: body digest, UTF-8 byte offsets and slice digest for each semantic span. It uses the Core operation and persists the returned receipt/IDs; its consumer opens only through the authorized Core proof. This is a new Buddy producer lease, not an expansion of #731.
4. PRIME separately plans schema/runtime adoption, exact data admission and product verification. The current live `0014` state and zero native rows remain unchanged by this design.

Stop if source bytes do not match the legacy revision digest; source artifact/revision identities or policy are ambiguous; the graph evidence is not an exact member with the required fields; an ID collision exists; the operation needs to change graph truth or historical legacy rows; existing authorization would be widened; the exact current `main` or dependency/PR ownership has moved; or a live database/corpus operation would be needed to finish this PR. Return that concrete discrepancy for a new owner decision.

## §6 Handoff after review

Report the design PR/base/head, independent review and disposition, exact contract choice, remaining unknown production metadata, implementation lease owner, and next Buddy producer lease. Until those later steps land, the legacy source pair remains catalogued but Session 22 has no native UTF-8 proof, and `source_unavailable` remains the correct consumer result.
