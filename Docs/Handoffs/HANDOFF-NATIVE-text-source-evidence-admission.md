# HANDOFF — NATIVE: atomic text-source and evidence admission

**Created:** 2026-09-27

**Status:** DESIGN PASS — bounded MIND implementation activated; implementation pending

**Owner:** DungeonMind; ARCHITECTURE designs, MIND stewards implementation, PRIME controls acceptance/merge

**Accepted design base:** `3ebdefaf1303089f21d3c94f2759df2d9274a71f` — PR #84 settlement

**Accepted runtime predecessor:** PR #83 merge `031b6650d0a506cf40f0189fc5cfac055ac37308`, reviewed head `decf694fc7304c30e82eae77a30247066c0f954a`, Cycle 2 PASS `5333897671`

**Settlement acceptance:** PR #84 head `6d149fcd5515e48d4b55b2c63beeddf9f7901283`, PRIME PASS `5333942899`

**Prospective topology:** serial, one DungeonMind implementation PR after activation

**Prospective title:** `NATIVE: atomically admit text sources and evidence`

**Approved design checkpoint:** `86e8f22d007df99de577cb412301c5a6d4e2d597`

**PRIME disposition:** DESIGN PASS, 2026-09-28; recorded from PRIME's explicit review of the approved checkpoint and its exact base above. No separate GitHub design review ID or design PR was required.

**Implementation activation:** one bounded DungeonMind implementation PR is authorized from the activated branch `codex/native-source-evidence-admission`, based on this approved checkpoint and current `main` `3ebdefaf1303089f21d3c94f2759df2d9274a71f`. No runtime code was present when this activation was recorded.

**Execution authorization:** PRIME authorizes only the V1 source/evidence admission and context-bound admitted-source preview capability specified here, including its machine-readable contract, ADR and owning-boundary proofs. This does not authorize source lifecycle, source-fresh governed writes, Keeper changes, Buddy changes, DEMO adoption or J3 activation.

## §1 One capability and its falsifier

From an initialized native KnowledgeSpace, one explicit admission operation
atomically persists exact UTF-8 source bytes, immutable revision/span proof, and
evidence membership in one new native child revision. The returned evidence IDs
are already in that exact child and can be used as the parent evidence of the
accepted Keeper preparation/commit path. They are not fabricated test records or
mere registered-source pointers.

No entities, assertions, aliases or semantic interpretation are created by this
operation. Admission of a source is not acceptance of its statements as world
truth. Source registration without evidence membership does not satisfy the slice.

The strongest falsifier is a durable result in which head/receipt/evidence says
success while the exact authorized body/span is missing, different, or partially
committed. A second is a purported Keeper proof that seeds evidence separately.
Proof must cross the real repository transaction and consumer boundary.

This intentionally joins body storage and evidence publication: either alone
leaves the selected first-source invariant false. It does not join semantic
extraction, graph assertions, product import, or later source lifecycle management.

## §2 Inventory and remaining limits

Accepted mechanisms available at the base:

- `initialize_empty_knowledge_space()` creates an empty native parent/head/receipt.
- Native CAS publication, durable receipt/replay, prospective reference allocation,
  materialization and exact-child reads already exist.
- `SourceArtifactV3`, `SourceRevisionV2`, `EvidenceRefV3` carry generic provenance.
- `KnowledgeSourceReader` pins a coherent epoch in O(1), then loads only requested
  artifacts/revisions. The in-memory versioned reader is a test double, not a
  native persistent source writer.
- Evidence admission checks source existence, declared metadata, visibility,
  active status and revision/artifact linkage. It does **not** require every
  historical evidence revision to equal the artifact's current revision.
- Native evidence/citation reads require admitted supporting assertions. An
  evidence-only parent must not be made to masquerade as an assertion citation.
- The frozen KnowledgeContribution V1 union has no evidence-add operation. This
  design uses a separately approved admission operation and canonical child
  builder, not a new union item or a reinterpretation of entity/assertion writes.

Missing: native source-body write/read authority, typed verified locations, a
joint source/evidence transaction, and a product consumer of that authority.
Persisted legacy source adapters remain World-shaped; adapting a locator string
or `can_open_source` flag is not source-body proof.

Consumer anchor: WorldKeeper `49a8620f066ce7ef8972a699020c012f50af9158`.
Its `DungeonMindWorldKeeperRuntime.prepare_change()` / `commit_prepared_change()`
consume evidence in the exact parent. Its preparation witnesses carry pointers,
not body digests or mutable source-policy epochs; commit does not consult a
`KnowledgeSourceReader`. This slice must **not** claim source-fresh governed-write
safety from that existing composition.

Buddy main at research anchor `eaa6292643b29d19afd83d69e471f6147432752b` still
pins DungeonMind `b83baf82c381b1929c2c7989326d667200ff544c` and the Keeper anchor
above. Buddy #785 is the sole serial DEMO implementation; its lease is not ours.
World-owned blank Plan is separately designed/blocked. Neither adoption nor J3
is activated by this handoff. No per-World database, fake campaign, seed graph,
legacy migration or deletion of previous DEMO artifacts is needed or authorized.

## §3 Ownership and explicit versioned prerequisite

The frozen V0 bundle and existing source/evidence/native graph schemas retain
their bytes and semantics. PRIME must approve this **additive durable contract**
before implementation activates. Do not smuggle typed locations into untyped
locator strings or silently change historical EvidenceRefV3 interpretation.

Proposed new companion family, defined in `contracts/vnext/native_source.py`:

- `dm_native_text_source_admission_v1`: bounded admission command.
- `dm_native_utf8_span_v1`: exact revision, body SHA, byte interval and slice SHA.
- `dm_native_source_admission_receipt_v1`: command fingerprint, allocation map,
  source authority epoch and existing typed KnowledgePublicationReceipt.
- `dm_native_source_access_v1`: context-bound authorized text preview or a
  non-disclosing unavailable result; not an assertion/citation admission result.

DungeonMind owns allocated artifact/revision/span/evidence identity, immutable
bytes and digests, generic visibility, evidence membership, transactions and reads.
Sources are globally identified; evidence membership is space-specific. Do not
add campaign/World ownership fields to SourceArtifactV3.

Buddy owns selection of the committed document revision, author/import workflow,
source classification, role-to-label mapping, semantic interpretation, extraction,
Plan edits, confirmation UI and product routing. It must later prove that the
submitted bytes/digest actually came from that exact saved document revision.
DungeonMind can verify supplied bytes; it cannot authenticate a separate Buddy
database merely because a caller supplied a document ID.

An optional generic origin record (`namespace`, opaque `object_id`, opaque
`revision_id`) is retained in the new admission record/receipt, not treated as
body proof or a Kernel dependency on Buddy Content types. Foreign references and
declared domain metadata remain explicit caller input, not inferred from paths.

## §4 Public operation, bounds, identities and read contract

Proposed public operation:

```text
publish_native_text_source_evidence(
    repository: NativeSourceEvidenceRepository,
    request: NativeTextSourceAdmissionV1,
    domain_contract,
    semantic_profile,
) -> NativeSourceAdmissionReceiptV1
```

Required command inputs: nonblank space/admission IDs; exact expected parent;
aware created-at; exact nonempty bytes and expected SHA-256; declared source
classification (a QualifiedTerm, not a new Kernel classification catalog),
authority, visibility, foreign refs/domain metadata; optional
origin; and 1–64 requested evidence spans. Each span has a unique caller-local
reference, explicit evidence role, start/end byte offsets and expected slice SHA.
One admission creates one new artifact and one immutable revision. Artifact
identity is not inferred/deduplicated from content, filename, title or origin.

V1 is bounded to at most 1,048,576 bytes of valid UTF-8 plain text/Markdown.
Preserve bytes exactly: no newline, Unicode, fence or whitespace normalization.
Intervals are half-open `[start_byte, end_byte)`, nonempty, in bounds, and both
ends must be UTF-8 boundaries. Whole-body evidence is an explicit interval, not
a different undocumented locator flavor. These bounds are proposed contract
decisions for PRIME, not already accepted runtime policy.

DungeonMind allocates typed, operation-bound identities and records the mapping
from each caller-local reference to span/evidence IDs. Caller-local refs are not
durable DM IDs. Hash collisions/identity collisions fail closed; never overwrite.
Allocation is namespaced by the complete `(space_id, admission_id, identity kind,
caller-local reference)` key, not admission ID alone. The same admission ID in
two spaces cannot reuse an artifact/revision/evidence allocation or receipt.
Global source IDs do not imply global evidence membership: the companion record
binds each allocation to its admitting space and child, whose evidence array is
the exact membership authority. This V1 cannot attach foreign existing IDs.

SourceRevisionV2 `body_storage` is `dm_native_utf8_body_v1`; native storage resolves
it by exact revision ID, never as a filename/URL to fetch. Span proof is a separate
typed immutable record referenced by EvidenceRefV3 `source_span_ref_id`. The
artifact starts active with its exact allocated current revision. Evidence has
that same explicit revision; verified spans set navigation capability flags.
Legacy locator fields may remain null; flags alone never authorize body opening.

This first slice has **no** public artifact-update, append-revision, retraction,
visibility-change, cross-space attachment, delete or source deduplication API.
Submitting another document revision creates another explicitly identified source,
not a silent update of the previous artifact. Historical sources remain intact.
Lifecycle/version advancement is a later separately designed capability.

The parent must be an existing native revision and the current expected head;
descriptors must match its exact domain/profile refs. Preserve all parent
entities/assertions/aliases/evidence, add only the admitted evidence, build/parse/
validate the canonical native child before publication, and preserve profile.
No implicit genesis, current-head fallback or V2→V3 transition.

Return the existing publication receipt nested in the companion receipt, exact
artifact/revision/span/evidence mapping, command SHA and committed source epoch.
The source receipt is not a second knowledge head or deployment registry.

Proposed `open_admitted_native_text(context, evidence_ref_id)` reads only evidence
membership in the exact supplied revision plus the same pinned native source
view. It verifies source declarations, active status, generic audience visibility,
revision linkage, body SHA and typed interval/slice SHA before returning bytes.
Missing, foreign-space, undeclared or unauthorized evidence returns the same
non-disclosing unavailable shape; corrupt admitted storage raises a safe integrity
error without body content. No raw-ID body bypass or filesystem/network read.

This is explicitly **admitted-source preview access**, even before a supporting
assertion exists. It does not weaken `EvidenceReadService` or create an assertion
anchor. After Keeper publication, existing assertion/evidence admission and anchor
services still decide whether a claim is citable; the new reader supplies its
verified source body. Product opens must construct a fresh authorized context;
within one operation, metadata and body use one pinned source epoch. Old coherent
contexts remain snapshots, not promises of real-time revocation enforcement.

## §5 Atomicity, replay and authority epochs

Add a native source/evidence repository port alongside, not by breaking, the
existing revision/source-reader protocols. The concrete composition shares the
same revision repository state/DB. A metadata writer followed by an independently
committed `publish_publication()` is expressly forbidden.

One transaction stages source artifact/revision/body/spans, child, normal
publication receipt, companion receipt, head/event and source epoch. Validate
before side effects. Under a documented lock order (source epoch then space),
verify exact parent, allocate identities and commit all or nothing. Reuse accepted
CAS/receipt semantics through transaction-scoped helpers; existing publication
entry points keep their observable behavior and regressions.

Store native body bytes in PostgreSQL for this bounded V1 so no external asset
store participates in the transaction. Add native tables; do not repurpose legacy
World/source tables or edit historical migrations. Tables require identity/foreign
key/uniqueness constraints and immutable version records. In-memory composition
must expose the same atomic visibility and rollback behavior, not mutate then
pretend failure erased observer-visible state.

The source epoch is repository-wide monotonic authority, changed in the same
transaction as native source changes. A coherent view pins it in O(1); requested
IDs use versioned/as-of records. Independent targeted queries into live tables
with a decorative epoch token are not coherent. No full-store preload/copy and
no source admission cache keyed only by knowledge revision. Fresh views see a
new admission; old views cannot partly acquire it. Epoch is not caller authority.

Same `(space_id, admission_id)` and exact canonical command returns the durable
original receipt/IDs, even after head advances; replay lookup precedes stale-parent
rejection. Changed bytes, span, policy, origin, parent or other command field with
the same operation ID is an idempotency conflict. Verify stored receipt/body
fingerprints on recovery. A lost post-commit response is outcome-unknown, not proof
of rollback: recover the same operation ID; never retry with new IDs automatically.

Invalid bytes/digest/span/declarations/descriptor mismatch fail before persistence.
Missing/legacy parent, stale head, identity collision, idempotency conflict,
persistence unavailable and outcome unknown remain distinct typed outcomes. Reuse
existing publication errors where their meaning is exact; define any needed native
source integrity/access error in the companion boundary. Do not leak source text,
private policy labels or raw storage diagnostics in public failures.

## §6 Activated implementation lease — one DungeonMind PR

Activation was recorded after re-anchoring current DungeonMind `main` at
`3ebdefaf1303089f21d3c94f2759df2d9274a71f` and confirming no open DungeonMind
implementation PR. The Buddy #785 lease is in another repository and does not
overlap this MIND-owned capability. Use branch `codex/native-source-evidence-admission`.
The machine-readable V1 contract and ADR ship with this implementation; no
contract-only or separate design PR is required.

New paths:

```text
src/dungeonmind/contracts/vnext/native_source.py
src/dungeonmind/application/vnext/native_source_admission.py
src/dungeonmind/application/vnext/native_source_access.py
src/dungeonmind/infrastructure/memory/vnext_sources.py
src/dungeonmind/infrastructure/postgres/vnext_sources.py
migrations/versions/0011_vnext_native_source_admission.py
tests/unit/test_vnext_native_source_admission.py
tests/unit/test_vnext_native_source_access.py
tests/integration/test_postgres_vnext_native_source_admission.py
scripts/verify_native_source_evidence_consumer.py
Docs/Contracts/vnext/dm_native_source_admission_v1.json
Docs/Decisions/ADR-0028-native-text-source-evidence-admission.md
Docs/Reports/REPORT-NATIVE-text-source-evidence-admission.md
```

Existing paths, only for additive exports/ports, shared atomic repository helpers,
required proof execution or changed authority claims:

```text
src/dungeonmind/contracts/vnext/__init__.py
src/dungeonmind/application/vnext/__init__.py
src/dungeonmind/application/vnext/ports.py
src/dungeonmind/application/vnext/errors.py
src/dungeonmind/infrastructure/memory/vnext_knowledge.py
src/dungeonmind/infrastructure/postgres/vnext_knowledge.py
tests/integration/test_migrations.py
.github/workflows/ci.yml
Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
Docs/Roadmaps/ROADMAP.md
Docs/Handoffs/HANDOFF-NATIVE-text-source-evidence-admission.md
```

Do not edit frozen source.py, dm_vnext_contract_v1.json, old migration files,
EvidenceReadService/source-anchor semantics, Buddy, Keeper, dependency pins or
other authority docs without explicit re-brief. New module/table/migration names
above are prospective; a newly landed migration/ADR requires re-anchor and an
explicit naming adjustment, not competing version numbers.

PR #84 already settled #83; no routine docs-only bookkeeping or repeated genesis
settlement is required. The implementation's authority edits describe this new
contract and current in-flight slice, never its future merge SHA/completion.
Re-anchor live main and open PRs again before opening the implementation PR, and
record any change to base, branch or competing leases. Use an isolated disposable
PostgreSQL target owned by this implementation lane; do not connect to Buddy's
persistent `54330`/`54331` DEMO pair.

## §7 Merge-blocking proof at the owning boundaries

1. **Exact request/bytes:** newline variants and multibyte Unicode round-trip;
   mismatch/invalid UTF-8/size limit/empty interval/mid-codepoint/out-of-bounds/
   duplicate local refs/undeclared policy or metadata fail with no mutation.
2. **Real admission:** public initializer → public admission → exact native
   child. No synthetic evidence parent; zero new entities/assertions/aliases;
   unchanged parent content; exact descriptors and requested evidence mapping.
3. **Atomic failure:** inject faults after staged source/body, child and receipt
   writes; rollback leaves no source, body, span, child, receipt, event or epoch
   increment. Confirm absence through public repository/read interfaces.
4. **Replay/recovery:** exact replay; every changed command class conflicts;
   replay after head advancement; lost response recovered after restart; two
   concurrent same-ID operations yield one result; different IDs against one
   parent yield one CAS winner and no orphan source from the loser.
   Same operation/local refs in two spaces produce isolated receipts/allocations;
   forced global ID collisions reject without clobbering the original space.
5. **Coherence:** two connections, a pinned pre-admission view and targeted
   post-admission view; old view sees none, new sees complete authority/body.
   Constant-work pin and bounded ID loads proven by counters/query inspection.
6. **Authorization/access:** exact-space membership and sealed audience; hidden,
   missing and foreign IDs non-disclosing; declarations and status enforced;
   digest/link/span corruption fails safely; preview does not confer claim
   admission; same text/different source/operation never silently coalesces.
7. **PostgreSQL:** upgrade from accepted 0010, preserve legacy/native prior
   revisions and receipts; real commit/rollback/concurrency/replay, close/reopen
   fresh connections and body read-back. Downgrade refuses populated new authority
   rather than deleting admitted bodies/evidence. Zero required-case skips.
8. **Actual Keeper contract:** executable consumer witness uses candidate
   DungeonMind and exact Keeper `49a8620f…` in an isolated environment, without
   changing either project's dependency manifest. Public initializer/admission
   create the parent; actual `DungeonMindWorldKeeperRuntime` prepares and explicitly
   commits one caller-specified object/fact with those returned evidence IDs and
   World-global scope `()`. Verify exact child/result bindings, ordinary native
   entity/assertion evidence read, typed source-body open, replay and PostgreSQL
   restart. Missing/foreign-parent evidence and stale parent reject. No seeded
   evidence, mocks of Keeper itself, provider call, campaign or direct graph write.
9. **Regression:** complete native initialization/publication/prospective/read/
   evidence/anchor suites; migration suite; full core/static checks and existing
   integration/benchmark CI. Frozen contract/schema hashes and accepted legacy
   behavior stay unchanged. Publish exact commands, versions, counts and skips.

The consumer script is required evidence, not an optional skipped pytest import.
The CI lease may add its isolated exact-pin invocation to integration verification;
record the resolved candidate-DM/accepted-Keeper import origins. Installing a
consumer to exercise its boundary is not a new runtime dependency or Keeper edit.

Synthetic text is an honestly labeled authored unit/contract fixture, not Of Conks
product acceptance. A later Buddy rehearsal uses the actual selected authored or
licensed parsed-Markdown revision; do not copy licensed corpus into this repo.

## §8 Product return, security gap and activation decision

Return to MIND/PRIME: pinned approved contract, accepted implementation/review/merge
SHAs when known, exact public APIs and allocation/error/replay rules, migration
revision, evidence/body proof and verified Keeper composition. Do not return an
unimplemented stub as the first-customer prerequisite.

This settles **authentic evidence-in-parent availability**, not the entire J3 gate.
Document editing and knowledge are separate durable steps. Source admission
advances a metadata/evidence child; later Keeper confirmation creates semantic
assertions in another child. If the latter fails, admitted evidence remains and
may be retried deliberately; never claim cross-step rollback or silent graph truth.
Buddy must make the two outcomes understandable and preserve the exact admitted
source/document/parent bindings. No source admission occurs merely on Plan Save.

Before J3 activation the owners must separately design source authorization and
freshness binding at Keeper preparation **and** governed commit. Existing pointer
witnesses alone cannot prove a source stayed authorized/current between operations.
V1 exposes no mutable native source lifecycle, but that restriction is not a
general source-freshness solution and does not license hidden evidence use.
Any required change to Keeper witnesses or DM governed-write fencing belongs to
an explicitly reviewed successor contract, not unplanned changes in this PR.

Also outstanding: truthful World-owned Plan, World-only Buddy Keeper composition,
dependency adoption, ordinary native Agent authority selection/citations, source
UI hydration, later-turn reads and restart in the same persistent DEMO DB pair.
V7/V8/V9 obligations for existing durable Worlds are unchanged. E5Q execution
parity and the deferred extraction semantic-ownership review remain separate lanes.

PRIME decision: **DESIGN PASS** for this bounded immutable V1 capability. PRIME
approved the additive typed companion family; exact UTF-8 bytes and typed span /
digest proof; evidence membership in the exact native child; one transaction for
source, head and both receipts; scoped deterministic allocation and replay; and
context-bound, non-disclosing admitted-source preview. Historical contribution,
source and evidence schema meanings remain unchanged. The proposed 1 MiB and
1–64 span limits are V1 input bounds and must be validated before Buddy product
acceptance.

The actual Keeper witness establishes that the returned evidence IDs can support
the exact native child without seeded evidence. It does not bind source-body
digest or mutable source-policy epoch across prepare/commit. That freshness gap
does not block this one-admission primitive and remains an explicit prerequisite
before any freshness-sensitive governed-write/J3 claim. A newly admitted source
does not authenticate Buddy's separate saved file; Buddy remains authoritative
for its selected bytes/revision and must later prove its own digest binding.
Source lifecycle, fresh-source governed-write safety, ordinary native citations,
DEMO adoption and J3 remain explicitly unaccepted.

## Stop conditions

False activation gate; competing serial lease; frozen-schema reinterpretation;
separate partial commits; raw-ID/private body access; seeded Keeper proof; automatic
assertions or source lifecycle; product/campaign vocabulary in Kernel; historical
revision mutation; required unleased owner change; skipped owning-boundary proof;
or representing this library result as full DEMO/J3/source-freshness acceptance.
Report the violated invariant, owner/path, missing proof and bounded re-brief.
