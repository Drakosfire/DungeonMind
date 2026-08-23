---
pr_body_template: |
  ## Handoff pointer
  - Workstream: CUTOVER / R.2b — governed adopted-source classification repair
  - Direction: DESIGN → CODE → REVIEW
  - Handoff: Docs/Handoffs/HANDOFF-cutover-adoption-source-classification-repair.md
  - Repository: Drakosfire/DungeonMind

  ## Exact predecessor truth
  - DungeonMind base: `b3f419b08676eaca763c8a75c374be6e96ee624e` (merge of PR #41 / R.2a).
  - Buddy R.3 PR #629 is paused at head `b9f8d33830d83cf1f9d557cadfcb614e9de9c1a8`.
  - Buddy Review Cycle 3 comment: `5387209676`.
  - Original sealed Eldyrwild adoption bundle fixture: `tests/fixtures/dungeonmind_dnd/eldyrwild_existing_world_adoption_bundle_v2.json`.
  - Original sealed bundle SHA-256: `90574dfc4101e4198c7fd96478d6f49e65aa534d0aa91fa41a9a17da9d49695f`.
  - Original adopted revision D_A: `rev:34b1f8e2625d5ba693fc726a2a1a4720`.

  Add one steward-supervised, atomic DungeonMind repair seam for an already-adopted
  V3 world whose adopted SourceArtifactV2 classification rows were mutated out of
  band and whose V3 membership checkpoint was then rewritten to bless those
  mutations. Preserve the original sealed adoption as historical truth, record
  one explicit source-classification fix-forward as new versioned authority, and
  produce a repair-aware effective adopted-membership checkpoint. Do not re-adopt,
  do not weaken V3, do not add a generic SourceArtifact mutation API, and do not
  change graph revisions or read semantics.
---

# HANDOFF — R.2b: governed adopted-source classification repair

**Created:** 2026-08-23  
**Status:** READY FOR IMPLEMENTATION  
**Workstream:** CUTOVER / World Graph runtime retirement prerequisite  
**Direction:** DESIGN → CODE → REVIEW  
**Repository:** `Drakosfire/DungeonMind`  
**Exact base:** `b3f419b08676eaca763c8a75c374be6e96ee624e` (PR #41 / R.2a merge)  
**Suggested branch:** `cutover/adoption-source-classification-repair`  
**Suggested PR title:** `CUTOVER: repair adopted source classification with an auditable checkpoint`  
**Inserted roadmap lane:** `R.2b` — surgical prerequisite discovered by Buddy R.3  
**Blocked successor:** Buddy R.3 / PR #629 — direct DungeonMind production reads  
**Later successor:** DungeonMind R.3a — direct-read optimization, only after R.3 semantic cutover is again viable

> **Dispatch ruling:** the live Eldyrwild data is not allowed to become the
> definition of what the original adoption “must have meant.” The exact sealed
> bundle remains historical authority for what was adopted. A legitimate
> classification correction must be represented as a later, explicit,
> tamper-evident DungeonMind operation.
>
> This is an exceptional adopted-history repair seam, not a general source
> editing API and not a second adoption.

---

## 1. Mission

Repair the authority model around one already-adopted world where two things
happened out of band during Buddy R.3 experimentation:

1. adopted `SourceArtifactV2` classification fields were changed directly in
   PostgreSQL; and
2. the V3 adoption receipt's `membership_sha256` was directly rewritten to
   match the mutated rows.

The known Eldyrwild mutations are:

```text
A. adopted SourceArtifactV2.visibility
   original sealed value: NULL / unknown
   out-of-band value:     gm

B. two session-less worldbuilding source artifacts
   original sealed campaign_id: campaign-owned
   out-of-band campaign_id:      NULL / world-owned
```

The Buddy scripts that performed these writes are now hard-disabled at R.3
head `b9f8d33830d83cf1f9d557cadfcb614e9de9c1a8`. That containment prevents a
repeat; it does not repair DungeonMind authority.

### Merge-ready invariant

After this PR, DungeonMind has one versioned, application-owned operation that
can prove and repair this state atomically:

```text
exact sealed adoption bundle
+ exact currently stored adoption receipt
+ exact current adopted-member rows
+ explicit source-classification repair intent
        ↓
strict preflight / no inference
        ↓
ONE writer-excluding transaction
        ↓
optional exact SourceArtifactV2 corrections
+ V4 adoption receipt
        ↓
original sealed membership checkpoint preserved
+ one explicit repair record
+ one effective adopted-membership checkpoint
```

No graph revision, graph head, source revision, contribution, identity decision,
review, or publication record changes.

---

## 2. Why the current state is invalid

### 2.1 V3 means the sealed bundle, not “whatever rows exist now”

`ExistingWorldAdoptionReceiptV3.membership_sha256` was deliberately introduced
as a checkpoint over the **exact sealed bundle's four adopted history families**:

```text
source artifacts
source revisions
contributions
identity decisions
```

It catches deletion, substitution, and coherent same-ID rewrites. A caller is
not allowed to mutate an adopted row and then rewrite the checkpoint from the
new database state; that destroys the historical claim the checkpoint exists
to make.

The existing v2→v3 promotion is explicit about this: expected membership is
derived from the exact sealed bundle, never minted from current database state,
and promotion changes only receipt representation — no history mutation.

### 2.2 SourceArtifactV2 was intentionally lossless

The original adoption's `visibility=None` is not a parser accident.
`SourceArtifactV2` intentionally keeps unknown producer axes nullable and does
not silently invent v1 defaults. `visibility` is DungeonMind access policy;
`source_visibility_state` is a separate producer classification.

That makes the R.3 discovery legitimate:

```text
Buddy historical product semantics were GM-only
but
DungeonMind's native fail-closed projection cannot infer GM from unknown
```

The correction may be reasonable. The way it was persisted was not.

### 2.3 Re-adoption is not the answer

The world is no longer pristine. D_A has descendants and DungeonMind is the
living authority. A second adoption would falsify chronology and collide with
existing adoption identity/head history.

### 2.4 Rewriting V3 again is not the answer

Restoring or changing only `membership_sha256` while leaving source rows
mutated merely chooses which side of the invariant is broken.

The repair needs a new versioned historical fact:

> this exact world was adopted from bundle B with checkpoint M0; later, under a
> steward-supervised repair operation, these exact source-classification fields
> were sanctioned as state M1.

---

## 3. Authority and exact predecessor truth

Read these before editing, in order:

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE.md`
3. `Docs/Roadmaps/ROADMAP.md`
4. `src/dungeonmind/contracts/evidence.py`
5. `src/dungeonmind/contracts/existing_world_adoption.py`
6. `src/dungeonmind/application/repositories.py`
7. `src/dungeonmind/application/existing_world_adoption.py`
8. `src/dungeonmind/application/existing_world_correspondence.py`
9. `src/dungeonmind/domain/existing_world_membership.py`
10. `src/dungeonmind/infrastructure/postgres/existing_world_adoption.py`
11. `src/dungeonmind/infrastructure/postgres/records.py`
12. `src/dungeonmind/infrastructure/memory/repositories.py`
13. `tests/fixtures/dungeonmind_dnd/eldyrwild_existing_world_adoption_bundle_v2.json`
14. Buddy PR #629 durable R.3 witness and Review Cycles 1–3, as incident evidence only.

### Locked factual anchors

```text
DungeonMind base / R.2a merge:
  b3f419b08676eaca763c8a75c374be6e96ee624e

sealed Eldyrwild bundle SHA-256:
  90574dfc4101e4198c7fd96478d6f49e65aa534d0aa91fa41a9a17da9d49695f

original adopted graph payload SHA-256:
  047214f19e3a2d22b1cf3e0596283844ef34853dd2e4f38d341c6b212ae320ef

original adopted revision D_A:
  rev:34b1f8e2625d5ba693fc726a2a1a4720

sealed adopted history:
  83 source artifacts
  83 source revisions
  93 GraphContributionV2 records
  13 IdentityDecisionRecordV2 records
```

The current head may be a descendant of D_A. **Repair must not require current
head == D_A and must not move the head.**

---

## 4. Locked design: V4 repaired-adoption receipt

### 4.1 V1/V2/V3 semantics remain frozen

Do not reinterpret V3. Do not change the meaning of
`ExistingWorldAdoptionReceiptV3.membership_sha256`.

Introduce a new contract only for the exceptional repaired state:

```text
ExistingWorldAdoptionReceiptV4
schema_version = dm_existing_world_adoption_receipt_v4
```

V4 retains every prior adoption fact and adds explicit repair authority.

### 4.2 V4 keeps two checkpoints with different meanings

Required semantics:

```text
membership_sha256
  = original adoption-time checkpoint M0
  = recomputed from the exact sealed bundle
  = historical fact; never rewritten from current rows

effective_membership_sha256
  = current sanctioned checkpoint M1
  = recomputed from the exact adopted member set after the authorized repair
```

This distinction is the center of the PR.

Do not overload one digest to mean both history and current authorized state.

### 4.3 V4 carries the exact adopted-member manifest

Add a small versioned value, preferred name:

```text
ExistingWorldAdoptionMembershipManifestV1
```

It contains sorted, unique exact IDs for the four adoption-time families:

```text
source_artifact_ids
source_revision_ids
contribution_ids
identity_decision_ids
```

Why this is required:

- a digest proves payload equality but cannot select which current rows belong
  to the original adoption once the world has descendants;
- the repair must hash the exact adopted set, not arbitrary later records;
- the manifest is derived only from the exact sealed bundle;
- this also removes the need for a frozen Buddy store merely to identify the
  adopted membership in future repair-aware consumers.

The manifest is not graph authority and does not make later records part of the
adoption.

### 4.4 V4 records exactly one source-classification repair

Keep v1 deliberately non-general. Preferred contract:

```text
ExistingWorldAdoptionSourceClassificationRepairV1
```

Minimum fields:

```text
schema_version
repair_id
reason_code = fix_forward_preexisting_source_classification_mutation
repaired_at
observed_pre_repair_membership_sha256
effective_membership_sha256
corrections[]
```

Each correction, preferred value name
`ExistingWorldAdoptionSourceArtifactClassificationCorrectionV1`, records:

```text
source_artifact_id
original_record_fingerprint
effective_record_fingerprint
changed_fields            # closed: visibility | campaign_id
original_visibility
effective_visibility
original_campaign_id
effective_campaign_id
```

The receipt fingerprint protects the complete repair record.

### 4.5 No repair chain in v1

V4 contains **one** repair record. Do not create a generic arbitrary repair
ledger or list-of-anything framework in this PR.

If another independent adopted-history repair is ever needed, design a new
contract from evidence then.

---

## 5. Repair intent: explicit, narrow, human-reviewable

The caller supplies the exact sealed bundle bytes plus a strict repair intent.
Preferred contract:

```text
ExistingWorldAdoptionSourceClassificationRepairIntentV1
```

The intent names exact source artifact IDs and only two possible operations:

```text
set_visibility_to_gm: true
clear_campaign_id: true
```

At least one must be true for each named artifact.

### 5.1 Allowed visibility repair

Only:

```text
sealed original visibility = None
→ effective visibility = Visibility.GM
```

No PLAYER→GM, GM→PLAYER, GM→None, or arbitrary visibility rewrite in v1.

### 5.2 Allowed campaign repair

Only:

```text
sealed original campaign_id = non-null
sealed original source_domain = worldbuilding
sealed original session_id = None
→ effective campaign_id = None
```

The caller must name the exact artifacts. DungeonMind must **not** infer
world-ownership from a Buddy ID prefix, filename, URI, `corpus:` convention, or
other product naming heuristic.

A source artifact whose generic `source_domain` is unknown/non-worldbuilding or
whose `session_id` is present is not eligible for this v1 campaign repair.
Stop rather than broaden the rule.

### 5.3 Everything else is immutable for this operation

For a repaired source artifact, all fields other than the specifically selected
`visibility` and/or `campaign_id` must equal the sealed bundle exactly:

```text
source_artifact_id
source_domain_key
source_domain
world_id
session_id
uri
current_revision_id
authority
artifact_kind
document_class
review_state
source_visibility_state
workspace_document_ref
lineage
status
created_at
updated_at
```

No status/current-revision lifecycle work belongs here.

---

## 6. Application seam

Preferred module:

```text
src/dungeonmind/application/existing_world_adoption_repair.py
```

Preferred entry point:

```text
repair_existing_world_adoption_source_classification(...)
```

Inputs:

```text
raw sealed ExistingWorldAdoptionBundleV2 bytes
repair intent
repair timestamp
ExistingWorldAdoptionRepository
GraphSnapshotReader
```

The application layer must:

1. parse the raw bundle through the existing canonical adoption parser;
2. require `ExistingWorldAdoptionBundleV2`;
3. recompute and bind exact bundle SHA;
4. derive original adopted membership M0 from the sealed bundle;
5. derive the exact adopted member manifest from the sealed bundle;
6. validate every requested correction against §5;
7. construct full target `SourceArtifactV2` models from the sealed originals —
   never from current database payloads;
8. derive deterministic original/effective fingerprints and a content-bound
   repair ID;
9. construct one repository command containing the original sealed facts,
   exact target artifacts, manifest, expected identities, and repaired_at;
10. delegate exactly once to the atomic repository operation;
11. reload/validate the returned V4 receipt;
12. on uncertain outcome, perform one exact repair-receipt probe and return only
    if the durable V4 repair identity matches exactly.

The application service does not execute SQL and does not mutate source records
through `SourceRepository.put_artifact()`.

---

## 7. Atomic repository unit of work

Extend the existing adoption aggregate port rather than inventing a general
source writer.

Preferred repository method:

```text
ExistingWorldAdoptionRepository.repair_source_classification(...)
```

The PostgreSQL implementation belongs with the existing-world adoption UoW,
not in an operator script and not as a generic `PostgresSourceRepository.update`.

### 7.1 Writer-excluding boundary

Use the same class of boundary already reviewed for V3 promotion:

```text
BEGIN
lock world row
LOCK TABLE source_artifacts,
           source_revisions,
           graph_contributions,
           identity_decisions
IN SHARE ROW EXCLUSIVE MODE
lock/re-read adoption receipt
...
COMMIT
```

If another table must be locked to make the proof true, document why. Do not
weaken isolation because the operation is “one time.”

### 7.2 Pre-mutation proof

Inside the transaction, before any write:

1. re-read and fingerprint-verify the stored adoption receipt;
2. require V3 corrupted-fix-forward state or exact V4 replay — no V1/V2;
3. require all non-membership V3 adoption facts to match the sealed bundle and
   referenced D_A exactly;
4. require the exact adopted graph revision still exists and matches receipt
   schema/payload digest;
5. load the exact adopted-member rows using the **sealed manifest IDs**, not
   “all current world rows” and not Buddy files;
6. require every adopted source revision, contribution, and identity decision
   to be fingerprint-equal to its sealed bundle record;
7. for each adopted source artifact:
   - if not named by the repair intent: current must equal sealed original;
   - if named: current must equal either sealed original or the exact derived
     target artifact;
   - any third state is corruption and aborts;
8. compute the currently observed adopted-member digest;
9. for a V3 fix-forward, require stored `membership_sha256` to equal that
   observed current digest. This proves the out-of-band receipt rewrite is at
   least internally bound to the currently observed adopted rows; otherwise the
   incident is more complex than this repair and must stop;
10. require no requested correction targets a non-adopted artifact.

Post-adoption descendants/extra rows are not members of this digest and are
never modified.

### 7.3 Mutation

Only after §7.2 succeeds:

- for each target artifact already equal to the exact effective model: no-op;
- for each target artifact still equal to the sealed original: update exactly
  its full relational identity columns, payload, and record fingerprint to the
  derived target model;
- do not call a generic mutable SourceArtifact API;
- do not mutate source revisions, contributions, identity decisions, evidence
  refs, graph revisions, or graph head.

Then recompute the exact adopted-member effective digest M1 inside the same
transaction.

### 7.4 Receipt swap

Replace the corrupted V3 receipt with V4 in the same transaction:

```text
V4.membership_sha256           = M0 from exact sealed bundle
V4.effective_membership_sha256 = M1 from exact target adopted membership
V4.membership_manifest         = exact IDs from sealed bundle
V4.source_classification_repair = exact repair record
```

Every v1/v2/v3 adoption fact other than the versioned representation must be
preserved.

### 7.5 Replay

If the stored receipt is already the exact V4 repair for the same sealed bundle
and intent, return it with zero writes.

If V4 exists but repair identity/target differs, fail with idempotency/integrity
conflict. No second repair is authorized.

---

## 8. Correspondence and effective membership

V3 behavior remains byte-for-byte semantic history.

Update `ExistingWorldCorrespondenceService` narrowly for V4.

### 8.1 Effective checkpoint

For V4, integrity checks over the current sanctioned adopted history compare the
exact manifest-selected rows to:

```text
effective_membership_sha256
```

Never to all current world rows. Later descendant records are not silently
folded into the adoption.

### 8.2 Original checkpoint

When validating the exact sealed original bundle against V4:

```text
bundle-derived M0 == receipt.membership_sha256
```

must still hold. This proves the original historical adoption was not rewritten
out of existence.

### 8.3 Source-history comparison

For V4 only, reconstruct the expected effective source artifacts by applying the
receipt's exact repair corrections to the sealed original bundle models.

A repaired artifact is a match only when:

```text
sealed fingerprint == correction.original_record_fingerprint
current fingerprint == correction.effective_record_fingerprint
changed fields are exactly the receipt-recorded allowed classification fields
all other fields equal sealed original
```

Do not globally ignore `visibility` or `campaign_id` drift.

### 8.4 V3 remains strict

Do not make `ExistingWorldCorrespondenceService` generally tolerant of source
history changes. Only an exact V4 repair authorizes the exact recorded drift.

---

## 9. Operator surface

No HTTP endpoint is needed.

Preferred steward-only CLI:

```text
scripts/repair_existing_world_adoption_source_classification.py
```

It is a thin caller of the application seam.

Required characteristics:

- dry-run by default;
- `--apply` is explicit;
- accepts database URL, exact sealed bundle path, and explicit repair-intent JSON;
- no direct SQL in the script;
- no import of Buddy;
- no frozen Buddy root;
- no live graph files;
- prints before/after receipt schema and safe digests/counts;
- prints the exact source artifact IDs and selected field transitions being
  requested (operator-local output, not metrics);
- exits non-zero on any unexpected drift;
- apply path delegates once to DungeonMind application authority.

The CLI must not infer corrections from current rows and then auto-apply them.
Human-reviewed intent is required.

---

## 10. Deployment / live repair sequencing

This distinction is critical:

> **The DungeonMind code PR may merge before the live repair is applied. The
> live repair must not be applied until the current Buddy hydrated-read consumer
> understands the V4 effective checkpoint.**

Why:

- Buddy R.3 is paused and the direct-read rollout gate is default-off;
- current production reads still use the hydrated compatibility path;
- that path currently expects a V3 receipt and uses `membership_sha256` as the
  served adopted-membership digest;
- V4 intentionally preserves original M0 in `membership_sha256` and carries M1
  separately as `effective_membership_sha256`.

Required rollout order:

```text
1. Merge this DungeonMind prerequisite code.
2. Return to Buddy PR #629.
3. Repin Buddy to the prerequisite merge.
4. Teach the legacy hydration/binding compatibility code to:
     - accept V4;
     - use effective_membership_sha256 for V4 serving/integrity;
     - retain V3 membership_sha256 behavior unchanged.
5. Prove the Buddy compatibility path against synthetic V3 + V4 receipts.
6. Backup / snapshot the live DungeonMind database.
7. Run the DungeonMind repair CLI dry-run against the exact sealed fixture and
   human-reviewed intent.
8. Require unexpected drift = 0.
9. Apply the repair once.
10. Re-read V4, original M0, effective M1, exact D_A, and current head.
11. Prove legacy hydrated reads still serve with direct-read gate off.
12. Rerun the R.3 direct-vs-legacy semantic witness from repaired authority.
```

Do not flip the direct-read rollout gate merely because this repair lands.
R.3a performance optimization remains separately required by the ~20s witness.

---

## 11. Exact Eldyrwild repair evidence

The repository already contains the exact sealed bundle fixture accepted by the
PostgreSQL adoption proof. Use it as the original-history oracle; do not
regenerate “equivalent” bytes from current Buddy state.

Required preflight pins:

```text
bundle file:
  tests/fixtures/dungeonmind_dnd/eldyrwild_existing_world_adoption_bundle_v2.json

bundle SHA-256:
  90574dfc4101e4198c7fd96478d6f49e65aa534d0aa91fa41a9a17da9d49695f

published D_A:
  rev:34b1f8e2625d5ba693fc726a2a1a4720

adopted membership counts:
  source artifacts:    83
  source revisions:    83
  contributions:       93
  identity decisions:  13
```

The implementation PR must **not** check the live database or a regenerated
current-world bundle into git.

A real live dry-run is operator evidence after code review; it is not CI input.

---

## 12. What this PR does NOT solve

Keep this prerequisite narrow.

It does **not** solve or reclassify the whole R.3 semantic witness.

The current Buddy witness still reports 199 blocking differences:

```text
169 provenance/scope differences
27 missing property-assertion differences
3 broken evidence-chain differences
```

This PR addresses only the authority/history correctness of the source
classification mutations already made during R.3 experimentation.

After the repaired state is authoritative, rerun the witness. Any remaining
169/27/3 classes are fresh evidence for a separate correction or explicit
design decision.

Specifically out of scope:

- populating missing v6 property assertions;
- repairing `node:cutover-canary` or other evidence-chain data;
- deciding that the remaining cross-campaign evidence semantics are acceptable;
- changing projection scope/admissibility semantics;
- changing R.1/R.2 retrieval semantics;
- read caching, batching, parsed-snapshot reuse, search index, anchor index;
- Buddy R.3 implementation changes;
- enabling the direct-read rollout gate;
- deleting Buddy hydration;
- generic SourceArtifact editing/lifecycle APIs;
- arbitrary source reclassification;
- a second existing-world adoption;
- a general history-repair framework;
- graph revision/head mutation;
- HTTP/admin product UI.

---

## 13. Expected file allowlist / write lease

Repository: `Drakosfire/DungeonMind` only.

| Action | Path | Purpose |
|---|---|---|
| Modify | `src/dungeonmind/contracts/existing_world_adoption.py` | V4 receipt + exact membership manifest + one source-classification repair value |
| Create | `src/dungeonmind/contracts/existing_world_adoption_repair.py` **or keep narrowly in existing adoption contract if cleaner** | Strict repair intent/command values; do not duplicate receipt definitions |
| Create | `src/dungeonmind/application/existing_world_adoption_repair.py` | Parse/bind sealed bundle, derive exact targets, call atomic repair UoW, recovery |
| Modify | `src/dungeonmind/application/repositories.py` | Add one adoption-aggregate repair operation; V4 durable receipt alias |
| Modify | `src/dungeonmind/application/existing_world_adoption.py` | V4 reload/compatibility; keep original adoption/promotion semantics frozen |
| Modify | `src/dungeonmind/application/existing_world_correspondence.py` | V4 exact repair-aware correspondence/effective checkpoint only |
| Modify | `src/dungeonmind/application/__init__.py` | Export narrow application seam if this repo's pattern requires it |
| Modify | `src/dungeonmind/infrastructure/postgres/existing_world_adoption.py` | Atomic PostgreSQL repair UoW + V4 reconstruction |
| Modify | `src/dungeonmind/infrastructure/postgres/__init__.py` | Export/wire only if constructor surface changes |
| Modify | `src/dungeonmind/infrastructure/memory/repositories.py` | Equivalent atomic in-memory repair semantics |
| Create | `scripts/repair_existing_world_adoption_source_classification.py` | Steward-only dry-run/apply wrapper; no SQL |
| Create/Modify | `tests/unit/test_existing_world_adoption_repair.py` | Contract/application/in-memory proof |
| Modify | existing adoption/correspondence contract tests selected during bounded discovery | V3 frozen + V4 behavior |
| Create/Modify | `tests/integration/test_postgres_existing_world_adoption_repair.py` | Owning PostgreSQL transaction/replay/failure proof |
| Create | `Docs/Decisions/ADR-0016-existing-world-adoption-repair.md` | Record why V3 stays historical and V4 carries explicit repair authority |
| Modify | `Docs/Architecture/AUTHORITY.md` | Add V4 repair authority after implementation truth exists |
| Modify | `Docs/Roadmaps/ROADMAP.md` | Mark R.2a landed; insert R.2b; R.3 blocked on repair; retain R.3a later |

### No migration expected

`existing_world_adoptions.schema_version`/payload already stores versioned
receipt JSON. Do not add a database migration merely to introduce a new receipt
schema.

If inspection proves a relational constraint makes V4 impossible without a
schema migration, **stop and review that fact before adding one**.

### Bounded discovery exception

At most four additional production/test paths, only when needed to wire the
existing adoption repository/bundle or existing contract round-trip tests.
Name every exception in the PR body.

No Buddy file may be edited in this PR.

---

## 14. Acceptance proof matrix

### 14.1 Contract

Prove:

- V1/V2/V3 parse/round-trip behavior unchanged;
- V4 rejects missing original/effective digests;
- V4 manifest IDs are sorted/unique/nonblank;
- repair correction IDs are unique and all belong to manifest;
- correction changed-fields vocabulary is closed;
- repair record effective digest equals receipt effective digest;
- repair record original digest equals V4 `membership_sha256`;
- no arbitrary extra fields.

### 14.2 Application validation

Prove:

- exact canonical bundle required;
- wrong bundle SHA / wrong world / wrong adoption id fails;
- non-v2 bundle fails;
- visibility repair only allows None→GM;
- campaign repair only allows campaign→None on session-less worldbuilding;
- unknown artifact id fails;
- duplicate correction fails;
- target artifact is derived from sealed original, not current DB;
- changing any unapproved SourceArtifact field fails before repository call.

### 14.3 Corrupted V3 fix-forward

Build a synthetic V3-adopted world, then **test-only** inject the exact incident
shape:

```text
mutate allowed SourceArtifactV2 classification fields
recompute their fingerprints
rewrite V3 membership_sha256 to the mutated adopted-member digest
```

That direct corruption setup is test scaffolding only. Production repair code
must never expose this mutation pattern.

Then prove the repair:

- recognizes exact sealed baseline;
- recognizes exact current corrupted digest;
- accepts only original-or-target source rows;
- produces V4;
- restores `membership_sha256` to sealed M0;
- sets `effective_membership_sha256` to M1;
- records exact correction fingerprints/fields;
- leaves D_A unchanged;
- leaves current descendant head unchanged;
- leaves source revisions/contributions/identity decisions unchanged;
- leaves non-adopted descendant records unchanged.

### 14.4 Unexpected corruption fails closed

Before calling repair, independently mutate one at a time:

```text
source uri
source status
source current_revision_id
source revision digest
contribution payload
identity decision payload
receipt bundle_sha256
receipt graph payload sha
published D_A graph payload
```

Every case must abort with zero repair writes.

### 14.5 Receipt is not allowed to lie twice

If current V3 `membership_sha256` does not equal the exact observed current
adopted-member digest, stop with integrity error. Do not guess whether the
receipt or rows are “more correct.”

### 14.6 Replay

```text
same sealed bundle + same repair intent
→ exact V4 receipt
→ no second source update
→ no second repair

changed intent after V4
→ conflict / integrity failure
→ no mutation
```

### 14.7 Atomic failure

Inject failures after each meaningful write stage. Any precommit failure leaves
all of:

```text
source artifacts
receipt schema/payload/fingerprint
head/revisions
```

exactly as before the repair attempt.

If a postcommit response is lost, one exact recovery probe may return the
matching V4 receipt. It must not infer success from source rows alone.

### 14.8 PostgreSQL

The owning integration proof uses real PostgreSQL and the actual transaction
boundary. In-memory tests support; they do not close the PR.

### 14.9 Exact fixture

Against the checked-in sealed Eldyrwild fixture, prove at minimum:

- exact bundle SHA pinned above;
- manifest counts 83 / 83 / 93 / 13;
- M0 is deterministic from exact sealed records;
- a synthetic allowed classification repair yields deterministic M1/V4;
- no Buddy checkout/files are needed.

Do not mutate a real/local Eldyrwild database in CI.

---

## 15. Full repository gates

Run all current standard gates, including:

```bash
uv run ruff check .
uv run pyright
uv run pytest
uv run --no-dev python -c "import dungeonmind"
```

and PostgreSQL integration CI.

Focused minimum:

```bash
uv run pytest tests/unit/test_existing_world_adoption_repair.py
uv run pytest tests/unit -k 'existing_world_adoption or correspondence'
uv run pytest tests/integration/test_postgres_existing_world_adoption_repair.py
```

The CLI must also prove:

```bash
uv run python scripts/repair_existing_world_adoption_source_classification.py --help
```

No live apply in CI.

---

## 16. Stop conditions

Stop and return to design/review if any of these occurs:

1. branch is not descended from `b3f419b08676eaca763c8a75c374be6e96ee624e`;
2. exact sealed fixture SHA differs from `90574dfc...`;
3. repair requires changing graph payload/revision/head;
4. repair requires changing source revisions, contributions, or identity decisions;
5. current V3 receipt differs from sealed adoption facts by anything other
   than the known membership checkpoint corruption;
6. current adopted source row differs from both sealed original and exact
   derived target;
7. current V3 membership digest does not equal the observed current adopted
   subset digest;
8. any requested field beyond visibility/campaign_id needs repair;
9. campaign repair targets a source that is not session-less worldbuilding;
10. a generic source-artifact update API appears necessary;
11. safe atomicity cannot be expressed through the adoption aggregate;
12. V4 requires a database schema migration — stop/review first;
13. implementation wants to derive target classifications from IDs/URIs/current
    rows rather than explicit intent;
14. implementation wants to re-adopt, delete history, or rewrite D_A;
15. implementation wants to fix the R.3 property/evidence/search/performance
    blockers in the same PR;
16. live repair is proposed before Buddy's hydrated compatibility reader can
    consume V4/effective membership;
17. applying the repair would silently enable direct production reads.

---

## 17. Definition of done

The code PR is merge-ready when this statement is true and proven:

> **DungeonMind can transform exactly one known-corrupted V3 adopted world into
> an explicit V4 repaired-adoption state under one atomic, writer-excluding
> operation, preserving the exact sealed adoption checkpoint as historical
> truth while recording a narrowly authorized source-classification repair and
> a separately verifiable effective adopted-membership checkpoint.**

The live incident is repaired only after the post-merge operator sequence in
§10 is completed successfully.

---

## 18. Return to Buddy R.3

After the DungeonMind prerequisite merges:

1. leave Buddy PR #629 paused;
2. repin it to the prerequisite merge;
3. add only the V4/effective-checkpoint compatibility needed by the still-live
   hydrated read path;
4. remove the dormant contract-violating SQL mutation implementation from the
   Buddy scripts rather than carrying it as historical recovery code;
5. apply/verify the DungeonMind live repair;
6. rerun the R.3 real-current semantic witness from repaired authority;
7. review the resulting blocker set from scratch.

Do **not** assume this repair makes the 199 blockers disappear. It makes the
authority state trustworthy enough that the next witness is meaningful.

Only after semantic cutover is again viable should R.3 complete, and only after
that should R.3a optimize the direct read architecture.
