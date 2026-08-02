# HANDOFF — B.2d Pinned Threat Create-or-Connect Contribution Plan

**Created:** 2026-08-01
**Status:** ACTIVE — dispatch exactly one DungeonMind-owned capability.
**Canonical handoff path:** `Docs/Handoffs/HANDOFF-b2d-pinned-threat-contribution-plan.md`
**Repository:** Drakosfire/DungeonMind
**Suggested branch:** `founding/pr-b2d-pinned-threat-contribution-plan`
**Implementation base:** `685d0f0b5547171c27bcdcf7d9a7961a1e268674`
**Predecessor:** merged PR `#8` — B.2c DungeonMindDnD Threat vocabulary and extraction candidates
**Suggested PR title:** B.2d: pinned Threat create-or-connect contribution plan
**One-line mission:** Given one validated D&D Threat candidate packet and one exact immutable `dm_union_graph_v3` revision, verify explicit graph references, propose deterministic exact-match create-or-connect identity outcomes, and emit a non-mutating, candidate-only `GraphContribution` preview pinned to that expected parent — without repository writes, durable identity decisions, fuzzy matching, graph materialization, or publication.

---

## §0 Executive implementation decision

B.2c established a strict, provenance-bearing Threat candidate packet and
authoritative catalog validation. The kernel already owns immutable graph
revisions, a durable `GraphContribution` envelope, and identity-decision
contracts. What was missing is the non-mutating bridge: verify explicit
existing-object references, propose create-or-connect identity outcomes from
exact label/alias matches only, and emit a candidate-only contribution
preview pinned to the expected parent revision.

The next PR must exercise graph-aware D&D planning without teaching the
DungeonMind kernel D&D semantics, without repository access from the profile
package, and without any durable write or publication path.

### Selected capability

```text
validated DndThreatCandidatePacket (B.2c)
+ exact StoredGraphRevision (dm_union_graph_v3)
+ configured GraphSnapshotReader (caller-supplied)
→ envelope/payload/world/schema/profile integrity verification
→ full unscoped graph parse
→ explicit existing-object verification by ID and kind
→ exact label/alias create-or-connect identity blocking
→ relationship endpoint resolution and duplicate-triple detection
→ machine-readable blockers OR candidate-only GraphContribution preview
→ expected_parent_revision_id pin (no append, no publish, no CAS)
```

### Why this is one capability

Candidate validation without graph context cannot verify existing endpoints,
propose connect outcomes, or detect duplicate relationship triples. Identity
blocking without a contribution preview leaves reviewers nothing concrete to
approve. A contribution preview without expected-parent pinning cannot be
safely committed later. These pieces therefore land together as one
profile-owned planning envelope rather than as scattered helpers.

### Explicitly rejected decompositions

| Alternative | Decision | Reason |
| --- | --- | --- |
| Add a kernel generic planner / interpretation layer | Reject | Reverses the B.2b/B.2c ownership boundary; no second-system evidence |
| Planner reads repositories or looks up current head | Reject | Profile package must stay repository-blind |
| Accept caller-scoped `ParsedGraphSnapshot` | Reject | Scoped graphs can hide existing objects and produce false `provisional_new` |
| Fuzzy, semantic, embedding, LLM, or confidence matching | Reject | Exact match only; ambiguity blocks |
| Cross-kind exact match with same-kind singleton present | Reject | Conservative: any cross-kind match blocks the whole candidate |
| Substitute missing explicit IDs via label matching | Reject | Explicit endpoints are stronger than blocking evidence |
| Silent merge / evidence augmentation for existing triples | Reject | Assertion-scoped augmentation is undesigned |
| Accepted or rejected assertions in the preview | Reject | Preview is candidate-only |
| Create `IdentityDecisionRecord` | Reject | Durable decisions belong to B.2e |
| Append contribution or publish revision | Reject | Materialization and CAS publication belong to B.2f |
| Change any file under `src/dungeonmind/` | Reject | Kernel contracts are sufficient; no kernel drift |
| Change profile/vocabulary catalog or candidate contracts | Reject | B.2c artifacts are immutable inputs |
| Add statblock, mechanics, LLM, or review UI | Reject | Out of scope successors |

### Governing invariant

The DungeonMind kernel remains completely unaware of D&D planning policy.
`dungeonmind_dnd` may depend one-way on a narrowly expanded kernel contract
surface for planning modules only. Every plan is non-canonical,
non-persisted, and non-publishable. Exact matching may **propose**
`resolved_existing` or `provisional_new`; it never **confirms** identity.
The plan pins `expected_parent_revision_id == base_revision_id` without
checking current head. Future commit remains responsible for stale-parent CAS.

### Mission falsification test

This is no longer one PR if it requires a kernel source change, a graph schema
change, a database migration, repository access from the profile package,
fuzzy matching, durable identity decisions, contribution append, graph
publication, LLM integration, review UI, vocabulary/catalog change, or a
generic interpretation layer.

## §1 Product outcome

After this PR, `dungeonmind_dnd` can reconcile one validated Threat candidate
packet against one exact immutable graph revision and produce a deterministic
`DndThreatContributionPlan` suitable for human or product review.

### API sketch

```python
from datetime import datetime
from dungeonmind.application.graph_snapshot import UnionGraphV3SnapshotReader
from dungeonmind.contracts.graph import StoredGraphRevision

from dungeonmind_dnd.application.contribution_planning import (
    plan_threat_candidate_contribution,
)

plan = plan_threat_candidate_contribution(
    packet,  # dict or DndThreatCandidatePacket
    stored_revision=stored,  # caller-fetched StoredGraphRevision
    graph_reader=reader,  # caller-configured GraphSnapshotReader
    actor="operator:gm-alice",
    planned_at=datetime(2026, 8, 1, 18, 0, tzinfo=UTC),
)
# plan.status → ready_for_review | blocked
# plan.proposed_contribution → GraphContribution | None
# plan.expected_parent_revision_id == plan.base_revision_id
```

The caller owns fetch authority. The planner never imports repositories,
never looks up current head, never appends, and never publishes.

### Tripod Null-Calf expected outcomes (happy path)

Against the synthetic Gatewatch base graph (`obj:north-gate` exists as
`dnd5e:location`; no Tripod or Breach objects yet):

| Record | Expected outcome |
| --- | --- |
| `cand:tripod-null-calf` | `provisional_new` → deterministic `obj:<32 hex>` |
| `cand:north-gate-breach` | `provisional_new` → deterministic `obj:<32 hex>` |
| `obj:north-gate` explicit endpoint | `verified` (`dnd5e:location`) |
| `candrel:tripod-located-at-north-gate` | `ready` |
| `candrel:tripod-participates-in-breach` | `ready` |
| `candrel:tripod-threatens-north-gate` | `ready` |
| Plan status | `ready_for_review`, zero blockers |
| Contribution preview | 10 assertions: 2 labels, 3 aliases, 2 summaries, 3 relationships |

If the base graph already contains a same-kind object whose label or alias
exactly matches a candidate term, that candidate becomes `resolved_existing`
instead of `provisional_new`. Any ambiguity, cross-kind collision, missing
explicit object, kind mismatch, duplicate packet triple, or pre-existing graph
triple blocks the whole plan.

### Contribution preview rules

When and only when the entire packet is blocker-free:

- `proposed_contribution` is a kernel `GraphContribution` preview.
- Every assertion is `acceptance_state=candidate`, `visibility=gm`,
  `epistemic_kind=asserted`.
- Node assertions carry the resolution outcome on label/alias/summary
  assertions (`resolved_existing` or `provisional_new`).
- Relationship assertions carry `identity_resolution_outcome=null`.
- `identity_decision_ids`, `unresolved_mentions`, and `diagnostics` are empty.
- `source_kind=extraction`; `status=active`; no supersession.
- Proposed object IDs for `provisional_new` are stable across replanning on
  a newer clean base (packet digest + candidate id; base revision excluded).

Blocked plans carry `proposed_contribution=null` and at least one
machine-readable blocker.

## §2 Why this is the next slice

PR #8 merged `dnd5e-profile-v2`, the Threat vocabulary catalog, strict
candidate contracts, deterministic validation, and prompt/schema material.
It deliberately left existing-object references unverified, identity
unresolved, and no contribution path.

The recommended minimal pipeline from graph-construction research is:

```text
schema-guided packet
→ typed node/edge candidates
→ deterministic validation            ← B.2c
→ exact candidate blocking / identity work
→ reviewable upsert or contribution planning   ← B.2d
→ publication
```

B.2d owns the fourth step for one narrow Threat slice: **pinned
create-or-connect planning** against a passed exact revision.

This PR also turns a product insight into a concrete planning decision:

> A reviewer must see what would be contributed before confirming identity.
> Therefore the preview is candidate-only, GM-visible, and pinned to the
> exact parent revision the commit will later require — but the planner
> itself never performs that commit.

That decision keeps identity confirmation, contribution persistence, and CAS
publication as separately testable successors.

## §3 Base, authority, and required reading

### Repository-state gate

Before editing:

```bash
git fetch origin
git checkout main
git pull --ff-only
git rev-parse HEAD
```

Expected base: `685d0f0b5547171c27bcdcf7d9a7961a1e268674` (merge commit for PR #8).

If main has moved, inspect every intervening DungeonMind PR for changes to:
`src/dungeonmind_dnd/`; contribution or identity contracts; graph snapshot
readers; import boundaries; roadmap/architecture ownership; any candidate,
contribution-planning, or publication work. Stop if another merged or open PR
already owns this capability.

### Read in this order

1. `Docs/Architecture/AUTHORITY.md` (§3.2 pinned contribution-plan authority)
2. `Docs/Architecture/ARCHITECTURE.md` (§6.3 profile-side graph planning layer)
3. `Docs/Decisions/ADR-0004-semantic-profile-boundary.md`
4. `Docs/Decisions/ADR-0005-dnd-profile-executable-boundary.md`
5. `Docs/Decisions/ADR-0006-pinned-profile-contribution-planning.md`
6. `Docs/Roadmaps/ROADMAP.md` (PR B.2d section)
7. `Docs/Handoffs/HANDOFF-b2c-dnd-threat-vocabulary-candidates.md`
8. PR #8 handback and merge commit
9. `src/dungeonmind/contracts/contribution.py`
10. `src/dungeonmind/contracts/graph.py`
11. `src/dungeonmind/contracts/identity.py`
12. `src/dungeonmind/application/graph_snapshot.py`
13. `src/dungeonmind_dnd/contracts/candidates.py`
14. `src/dungeonmind_dnd/application/threat_candidates.py`
15. `tests/unit/test_import_boundaries.py`
16. `tests/fixtures/dungeonmind_dnd/tripod-null-calf-threat-candidates-v1.json`
17. Project Source `LLM-graph-construction.md`, especially identity-blocking and contribution-planning sections

### Authority precedence

1. Current checked-in DungeonMind contracts, ADRs, architecture, and code
2. Merged repository state at `685d0f0b...`
3. This checked-in handoff
4. Existing tests and synthetic fixtures
5. `LLM-graph-construction.md` as design/research evidence
6. DungeonMindBuddy Threat/statblock documents as consumer requirements only
7. Chat summaries

DungeonMindBuddy documents do not authorize kernel changes or repository
access from the profile package.

## §4 Ownership and dependency boundary

### DungeonMind kernel continues to own

- strict shared contract base
- evidence/source contracts
- semantic-profile identity and descriptor contracts
- graph revision envelope and stored-revision contracts
- `GraphContribution` and assertion contracts
- identity outcome enums (shared vocabulary only)
- graph snapshot parsing (`GraphSnapshotReader`, `ParsedGraphSnapshot`)
- canonical JSON hashing
- graph identity, revisions, retrieval, admission, projection (runtime)
- capability policy

**No kernel runtime or contract file changes in this PR.**

### DungeonMindDnD gains one additional executable capability

- D&D Threat contribution-plan contracts (`DndThreatContributionPlan` and records)
- pure create-or-connect planner (`plan_threat_candidate_contribution`)
- package-owned planning error (`DndContributionPlanningError`)
- synthetic Gatewatch graph fixture and expected plan fixture

B.2c modules (`threat_candidates`, candidate contracts, vocabulary) remain
unchanged except through re-use by the planner.

### One-way dependency rule

After this PR:

```text
dungeonmind_dnd (B.2c modules)
  may import:
    dungeonmind.contracts.base
    dungeonmind.contracts.evidence
    dungeonmind.contracts.semantic_profile
    dungeonmind.domain.canonical
    stdlib
    pydantic

dungeonmind_dnd (B.2d planning modules only:
  application/contribution_planning.py
  contracts/contribution_planning.py)
  may additionally import:
    dungeonmind.application.graph_snapshot
    dungeonmind.contracts.contribution
    dungeonmind.contracts.graph
    dungeonmind.contracts.identity
    dungeonmind.contracts.vocabulary

dungeonmind_dnd
  may not import:
    dungeonmind.application.repositories
    dungeonmind.infrastructure
    dungeonmind.service
    dungeonmind.agents
    FastAPI
    PostgreSQL/pgvector
    model/provider SDKs

dungeonmind
  may never import dungeonmind_dnd
```

The expanded allowlist applies **only** to the two B.2d planning modules.
All other `dungeonmind_dnd` files retain the B.2c narrow allowlist.

### Repository-blind rule

The planner receives:

- one `StoredGraphRevision` (revision envelope + raw payload bytes)
- one configured `GraphSnapshotReader`

It never fetches revisions, never reads current head, never opens a database
connection, and never appends or publishes. Callers that need live graph state
must fetch the revision themselves and pass it in.

## §5 New contracts summary

Create `src/dungeonmind_dnd/contracts/contribution_planning.py`. All models
inherit `DndCandidateContractModel` (`extra="forbid"`).

### Enums

| Enum | Values | Role |
| --- | --- | --- |
| `DndThreatPlanStatus` | `ready_for_review`, `blocked` | Whole-plan lifecycle |
| `DndExistingObjectVerificationState` | `verified`, `missing`, `kind_mismatch` | Explicit endpoint check |
| `DndRelationshipPlanState` | `ready`, `endpoint_blocked`, `duplicate_in_packet`, `already_exists_in_graph` | Relationship planning |
| `DndPlanBlockerCode` | `ambiguous_identity`, `cross_kind_collision`, `existing_object_missing`, `existing_object_kind_mismatch`, `relationship_endpoint_blocked`, `duplicate_packet_relationship`, `relationship_already_exists` | Machine-readable blockers |
| `DndMatchChannel` | `label`, `alias` | Exact-match provenance |

### Core models

| Model | Schema | Key fields |
| --- | --- | --- |
| `DndCandidateResolution` | `dmdnd_candidate_resolution_v1` | `candidate_id`, `candidate_kind`, `outcome`, `target_object_id`, `matched_object_ids`, `match_channels`, `confirmation_required=true` |
| `DndExistingObjectVerification` | `dmdnd_existing_object_verification_v1` | `existing_object_id`, `expected_kind`, `actual_kind`, `state`, `relationship_candidate_ids` |
| `DndRelationshipPlan` | `dmdnd_relationship_plan_v1` | `relationship_candidate_id`, `predicate`, `subject_object_id`, `object_object_id`, `state`, `existing_relationship_ids` |
| `DndPlanBlocker` | `dmdnd_plan_blocker_v1` | `code`, optional IDs, `related_object_ids` — no prose |
| `DndThreatContributionPlan` | `dmdnd_threat_contribution_plan_v1` | pins, resolutions, verifications, plans, blockers, optional preview-content digest and `proposed_contribution` |

### Key contract rules

- Allowed identity outcomes in resolutions:
  `resolved_existing`, `provisional_new`, `ambiguous`, `blocked_collision`.
  Durable outcomes (`created_new`, `merged`, etc.) are forbidden.
- `confirmation_required` is always `true` on resolutions and the plan.
- `expected_parent_revision_id` must equal `base_revision_id`.
- `base_graph_schema` must be exactly `dm_union_graph_v3`.
- Digest fields are 64-char lowercase hex.
- `plan_id` is `plan:<32 hex>`; proposed object IDs are `obj:<32 hex>`.
- Blocked plans derive `plan_id` from packet/base/actor/time; ready plans also
  bind `preview_content_sha256`, a canonical digest of the complete preview
  content with derived contribution/assertion IDs excluded.
- Plan records carry IDs, qualified terms, and digests only — never labels,
  aliases, summaries, evidence locators, or source prose.
- Blockers correspond bijectively to bad resolution/verification/relationship
  records (no orphan blockers).
- `ready_for_review` requires zero blockers and a non-null
  `proposed_contribution`. `blocked` requires blockers and null contribution.
- Contribution preview invariants: candidate-only assertions, GM visibility,
  asserted epistemic kind, empty identity/unresolved/diagnostics fields,
  complete node coverage (one label per resolution, unique aliases and at most
  one summary), unique assertion IDs, and content-digest verification.

## §6 Planner API and execution order

Create `src/dungeonmind_dnd/application/contribution_planning.py`.

### Public API

```python
def plan_threat_candidate_contribution(
    payload: Mapping[str, Any] | DndThreatCandidatePacket,
    *,
    stored_revision: StoredGraphRevision,
    graph_reader: GraphSnapshotReader,
    actor: str,
    planned_at: datetime,
) -> DndThreatContributionPlan:
    ...
```

Deterministic: same packet, stored revision, actor, and `planned_at` →
byte-identical plan. `planned_at` is caller-supplied operation identity;
exact retries must reuse it.

### Execution order (13 steps)

1. **Parse and validate packet** — `parse_threat_candidate_packet` +
   `validate_threat_candidate_packet` (B.2c). Failures →
   `DndContributionPlanningError`.
2. **Verify revision envelope digest** — recompute payload SHA-256; must match
   `revision.graph_payload_sha256`.
3. **Verify world agreement** — envelope world, payload `world_id`, and packet
   `world_id` must agree.
4. **Require plannable schema** — `revision.graph_schema == dm_union_graph_v3`.
5. **Parse full stored payload** — through supplied `graph_reader`; no scoped
   snapshot input. Parser failures → sanitized planning error.
6. **Require profile pin match** — graph `semantic_profile_ref` must equal
   packet `semantic_profile`.
7. **Resolve candidate identities** — exact label/alias blocking (§7).
8. **Verify explicit existing endpoints** — by ID and kind (§8).
9. **Plan relationships** — endpoint resolution + duplicate detection (§9).
10. **Collect blockers** — one per non-reviewable record; sort deterministically.
11. **Compute blocked plan_id** — digest of packet, base revision, actor,
    `planned_at`; blocked plans return without a preview.
12. **Build preview content** — only if zero blockers (§10), then compute its
    canonical content digest.
13. **Compute ready plan_id** — bind the preview content digest to the request
    fingerprint and rebuild derived contribution/assertion IDs.
14. **Assemble plan** — sorted child records; validate complete preview binding.

Integrity failures raise `DndContributionPlanningError` and produce no plan.
Valid-but-unresolvable states yield a `blocked` plan.

## §7 Exact identity-resolution policy

### Normalization

Identity terms normalize with `term.casefold().strip()` only — identical to
the graph snapshot index rule. No fuzzy edit distance, phonetic matching,
token reordering, or summary comparison.

### Match material per candidate

For each node candidate, collect normalized terms in order:

1. normalized label
2. normalized surface forms (deduplicated, label-equivalent forms skipped in preview only)

### Packet-internal collision (pre-graph)

If any normalized term overlaps between two candidates in the same packet,
**both** candidates become `ambiguous` before graph matching begins.

### Graph matching

For each non-colliding candidate:

| Condition | Outcome |
| --- | --- |
| Zero graph matches | `provisional_new` with deterministic `obj:<32 hex>` from `(world_id, packet_digest, candidate_id)` |
| Exactly one match, same kind | `resolved_existing` targeting that object |
| Two or more matches, all same kind | `ambiguous` |
| Any match of different kind | `blocked_collision` (even if exactly one same-kind match also exists) |

Match channels record whether the hit came from label index or alias index.

### Provisional ID stability and collision guards

- Proposed IDs exclude base revision id so replanning on a newer revision
  does not churn proposed object identities.
- If two candidates would receive the same proposed ID → planning error.
- If a proposed ID already exists in the graph → planning error.

### Explicit non-behavior

- No confidence scores or ranking among matches.
- No relationship-inferred identity.
- No summary-based matching.
- No substitution of explicit `existing_object_id` endpoints.

## §8 Existing-object endpoint verification

Every packet relationship endpoint of the form
`{"existing_object_id": "...", "expected_kind": "..."}` is verified directly
against the parsed full snapshot.

| State | Condition |
| --- | --- |
| `verified` | Object exists and `actual_kind == expected_kind` |
| `missing` | No object with that ID |
| `kind_mismatch` | Object exists but kind differs |

Rules:

- Verification is by exact ID only — never label-matched or fuzzy-substituted.
- A missing explicit ID never becomes `provisional_new`.
- Each unique `(existing_object_id, expected_kind)` pair appears once in
  `existing_object_verifications`, sorted deterministically, listing all
  referencing relationship candidate IDs.
- Missing or kind-mismatched explicit endpoints block the whole plan and emit
  `existing_object_missing` or `existing_object_kind_mismatch` blockers.
- Endpoint-blocked relationships emit `relationship_endpoint_blocked` blockers.

## §9 Relationship planning

For each candidate relationship, resolve subject and object endpoints:

- **Candidate endpoint** → use `target_object_id` from that candidate's
  resolution (may be null if identity blocked).
- **Existing endpoint** → use verified object ID, or null if verification failed.

Then classify:

| State | Condition |
| --- | --- |
| `endpoint_blocked` | Either endpoint unresolved |
| `duplicate_in_packet` | Same `(subject_id, predicate, object_id)` triple appears more than once among resolved packet relationships |
| `already_exists_in_graph` | Exact triple already present in base graph |
| `ready` | Endpoints resolved, triple unique in packet, triple absent from graph |

Rules:

- Direction comes entirely from the validated packet; never inverted.
- Existing graph triples **block** — silent merge and evidence augmentation are
  forbidden because assertion-scoped augmentation semantics are not designed.
- Same subject/object with different predicates is allowed (e.g. `located_at`
  and `threatens` to the same location).
- `existing_relationship_ids` populated only for `already_exists_in_graph`.

## §10 Contribution-preview construction

Built only when the plan has zero blockers.

### Contribution envelope

- `contribution_id` = `contrib:<32 hex>` derived from `plan_id`
- `world_id`, `campaign_scope`, source artifact/revision from packet
- `extraction_profile` = `{profile_id}@{revision}|{vocab_id}@{revision}|sha256:{catalog_digest}`
- `produced_at` = `planned_at`
- `authored_by` = `actor`
- `source_kind=extraction`, `status=active`, no supersession

### Assertions (packet order)

**Per node candidate:**

1. one `label` assertion on resolved target object
2. one `alias` assertion per non-label-equivalent surface form
3. one `summary` assertion if present

**Per relationship candidate:**

1. one `relationship` assertion with resolved subject/object IDs and exact predicate

Every assertion:

- `acceptance_state=candidate`
- `visibility=gm`
- `epistemic_kind=asserted`
- closed evidence refs copied from the packet
- node field assertions carry `identity_resolution_outcome` from the resolution
- relationship assertions carry `identity_resolution_outcome=null`

Assertion IDs are deterministic from contribution id, candidate id, kind, and
discriminator.

Ready `plan_id` additionally commits to a canonical digest of every semantic
preview field: node labels, aliases, summaries, relationship endpoints and
predicates, evidence records, packet source anchors, contribution metadata, and
the plan's resolution/verification/relationship records. Derived contribution
and assertion IDs are excluded from that digest because they are derived from
`plan_id`. Reloaded plans therefore reject content mutations even when a
non-empty evidence list or the original assertion ID is retained.

## §11 Failure and sanitization model

Add `DndContributionPlanningError` to `src/dungeonmind_dnd/domain/errors.py`.

### Raises `DndContributionPlanningError` (no plan produced)

- Blank actor
- Candidate packet validation failure
- Vocabulary integrity failure
- Payload digest mismatch
- World mismatch (envelope/payload/packet)
- Unsupported graph schema (not v3)
- Unparseable stored payload
- Profile ref mismatch
- Proposed object ID collision (within packet or with graph)
- Plan or contribution contract invariant violation

### Yields `blocked` plan (valid inputs, human review required)

- Ambiguous identity (including packet-internal term collision)
- Cross-kind collision
- Missing or kind-mismatched explicit object
- Endpoint-blocked, duplicate-in-packet, or already-exists-in-graph relationships

### Sanitization rules

Error `details` and raised messages identify:

- packet/candidate/relationship/object/plan/revision IDs
- qualified terms, schema/profile/vocabulary IDs, digests
- exception type names and validator message strings

They must **never** echo:

- labels, aliases, summaries
- source or graph prose
- evidence locators or URIs
- raw rejected payloads
- filesystem paths
- Pydantic `errors()` input values
- chained parser exceptions (always `from None`)

Contract models for resolutions, verifications, blockers, and the plan itself
similarly exclude prose fields by construction.

## §12 Synthetic proof fixtures

### Gatewatch base graph

Create `tests/fixtures/dungeonmind_dnd/gatewatch-world-graph-v3.json`.

Synthetic world `world:synthetic-gatewatch` with `dm_union_graph_v3` payload:

- `obj:north-gate` — `dnd5e:location`, label "North Gate", alias "Old North Gate"
- `obj:gatewatch-keep` — `dnd5e:location`
- `obj:gatewatch-mustering` — `dnd5e:encounter`
- one existing relationship: mustering `located_at` keep
- pinned `dnd5e-profile-v2` semantic profile ref
- synthetic `fixture://` evidence locators only

No Tripod Null-Calf, no North Gate Breach, no mechanics/statblock fields.

### Expected plan fixture

Create `tests/fixtures/dungeonmind_dnd/tripod-null-calf-contribution-plan-v1.json`.

Uses the B.2c packet fixture unchanged. Expected happy-path plan with:

- both node candidates `provisional_new`
- `obj:north-gate` verified
- three relationships `ready`
- ten candidate-only contribution assertions
- `expected_parent_revision_id == base_revision_id`
- fixed `actor` and `planned_at` for byte-stable replay

### Inputs reused unchanged

- `tests/fixtures/dungeonmind_dnd/tripod-null-calf-threat-candidates-v1.json` (B.2c)
- `src/dungeonmind_dnd/profiles/dnd5e-v2.json`
- `src/dungeonmind_dnd/vocabularies/threat-v1.json`

## §13 Deterministic proof matrix

Property-based testing is not required. Exact table-driven tests are sufficient.

### Happy path and determinism

| Case | Expected result |
| --- | --- |
| Valid packet + Gatewatch fixture | `ready_for_review`; matches expected plan fixture byte-for-byte |
| Exact replay | Second call byte-identical to first |
| Replan on newer base (+ unrelated node) | Same proposed object IDs; different `plan_id` and `contribution_id` |
| Contribution preview shape | 2 label + 3 alias + 2 summary + 3 relationship assertions; all candidate/gm/asserted |

### Candidate identity

| Case | Expected result |
| --- | --- |
| Exact same-kind label match | `resolved_existing` via `label` channel |
| Exact same-kind alias match | `resolved_existing` via `alias` channel |
| Two same-kind label matches | `blocked`; `ambiguous_identity` |
| Wrong-kind exact label match | `blocked`; `cross_kind_collision` |
| Same-kind + wrong-kind both match | `blocked`; `cross_kind_collision` |
| Packet candidate term collision | `blocked`; `ambiguous_identity` on both |
| Typo label ("Tripod Null Calf") | `provisional_new` (no fuzzy match) |
| Graph summary resembles candidate summary | `provisional_new` (no summary match) |

### Existing endpoints

| Case | Expected result |
| --- | --- |
| Valid `obj:north-gate` | `verified` |
| Missing explicit object | `blocked`; `existing_object_missing` + endpoint blockers |
| Wrong kind on explicit object | `blocked`; `existing_object_kind_mismatch` |
| Missing ID while similar label exists | `blocked`; ID verification only |

### Relationships

| Case | Expected result |
| --- | --- |
| Duplicate packet triple | `blocked`; `duplicate_packet_relationship` |
| Triple already in graph | `blocked`; `relationship_already_exists` |
| Same endpoints, different predicates | `ready` (happy path) |

### Integrity failures (raise, no plan)

| Case | Expected result |
| --- | --- |
| Blank actor | `DndContributionPlanningError` |
| Payload digest mismatch | `DndContributionPlanningError` |
| Packet/revision world mismatch | `DndContributionPlanningError` |
| Graph schema v1 or v2 | `DndContributionPlanningError` |
| Profile revision mismatch | `DndContributionPlanningError` |
| Proposed ID collides with existing object | `DndContributionPlanningError` |
| Malformed v3 payload | Sanitized `DndContributionPlanningError` |

### Sanitization

| Case | Expected result |
| --- | --- |
| Sentinel labels/summaries/locators in failure paths | Absent from error str/repr/traceback/details |

## §14 Import-boundary evolution

Modify `tests/unit/test_import_boundaries.py`:

- Retain: kernel never imports `dungeonmind_dnd`.
- Retain: B.2c modules import only narrow contract/canonical allowlist.
- Add: `DND_PLANNING_MODULES` frozenset for the two B.2d modules.
- Add: `DND_PLANNING_ALLOWED_KERNEL_MODULES` = B.2c allowlist plus
  `graph_snapshot`, `contribution`, `graph`, `identity`, `vocabulary` contracts.
- Add: path-sensitive allowlist function `_dnd_allowed_for(module_name)`.
- Add: `test_dnd_planning_modules_never_import_repositories_or_infra`.
- Add: `test_dnd_planning_import_loads_no_optional_dependencies`.

Also prove:

```bash
uv run --no-dev python - <<'PY'
import sys
import dungeonmind
assert "dungeonmind_dnd" not in sys.modules
PY
```

and:

```bash
uv run --no-dev python - <<'PY'
import sys
import dungeonmind_dnd.application.contribution_planning
for forbidden in ("fastapi", "psycopg", "sqlalchemy", "openai", "anthropic"):
    assert forbidden not in sys.modules
PY
```

Importing planning modules must not load repositories, infrastructure, or
optional provider/database/API dependencies.

## §15 Files in scope — exact allowlist

| Action | Path | Purpose |
| --- | --- | --- |
| Create | `Docs/Handoffs/HANDOFF-b2d-pinned-threat-contribution-plan.md` | Canonical implementation handoff |
| Create | `Docs/Decisions/ADR-0006-pinned-profile-contribution-planning.md` | Planning boundary decision |
| Modify | `Docs/Architecture/ARCHITECTURE.md` | §6.3 profile-side graph planning layer |
| Modify | `Docs/Architecture/AUTHORITY.md` | §3.2 pinned contribution-plan authority |
| Modify | `Docs/Roadmaps/ROADMAP.md` | B.2c landed; B.2d current; named successors |
| Modify | `README.md` | Truthful planning capability and non-goals |
| Modify | `CONTRIBUTING.md` | Path-sensitive B.2d import allowlist |
| Modify | `src/dungeonmind_dnd/__init__.py` | Export planning API if appropriate |
| Modify | `src/dungeonmind_dnd/contracts/__init__.py` | Export plan contracts |
| Modify | `src/dungeonmind_dnd/application/__init__.py` | Export planner |
| Modify | `src/dungeonmind_dnd/domain/__init__.py` | Export planning error |
| Modify | `src/dungeonmind_dnd/domain/errors.py` | `DndContributionPlanningError` |
| Create | `src/dungeonmind_dnd/contracts/contribution_planning.py` | Plan record contracts |
| Create | `src/dungeonmind_dnd/application/contribution_planning.py` | Pure planner |
| Create | `tests/fixtures/dungeonmind_dnd/gatewatch-world-graph-v3.json` | Synthetic base graph |
| Create | `tests/fixtures/dungeonmind_dnd/tripod-null-calf-contribution-plan-v1.json` | Expected happy-path plan |
| Create | `tests/unit/test_dnd_threat_contribution_planning.py` | Planning matrix |
| Create | `tests/unit/test_dnd_threat_contribution_plan_contract.py` | Contract invariants |
| Create | `tests/unit/test_dnd_threat_contribution_plan_sanitization.py` | Failure sanitization |
| Modify | `tests/unit/test_import_boundaries.py` | Path-sensitive allowlist |

Conditional path: `uv.lock` must not change. No dependency is added.

### Hard forbidden paths

No file under these paths may change in this PR:

```text
src/dungeonmind/
migrations/
src/dungeonmind_dnd/profiles/
src/dungeonmind_dnd/vocabularies/
src/dungeonmind_dnd/contracts/candidates.py
src/dungeonmind_dnd/contracts/vocabulary.py
src/dungeonmind_dnd/application/threat_candidates.py
```

If a kernel contract change appears necessary, stop and re-decompose.

## §16 Atomic documentation sync summary

Documentation is merge-blocking and must land in the same PR.

### ADR-0006

Record: graph-aware D&D planning allowed only over a passed exact stored
revision; profile package remains repository-blind; full unscoped payload
required; exact label/alias matching is blocking evidence not final authority;
conservative cross-kind blocking; explicit existing IDs verified directly;
existing triples block; ready plans contain candidate-only contribution
preview; expected parent pinned without CAS check; no
`IdentityDecisionRecord`. Rejected: kernel generic planner, scoped snapshots,
repository lookup, fuzzy matching, automatic merge, accepted assertions in
preview, direct save/publish, catalog change.

### Architecture (§6.3)

Add profile-side graph planning layer: reconcile validated Threat packet
against one exact revision; emit deterministic plan with candidate-only preview
when entirely safe; repository-blind; exact match proposes never confirms;
explicit IDs stronger than label match; existing triples block; expected
parent pinned not CAS-checked.

### Authority (§3.2)

Add: exact immutable base revision is authority for existing object/relationship
presence during planning; catalog remains term authority; candidate evidence
remains claim authority; exact matching is proposal mechanism; plan and preview
are not canonical.

### Roadmap

Update:

```text
B.2c  Threat vocabulary + candidates ✅
B.2d  pinned create-or-connect contribution plan ← current
```

Name successors: B.2e review adoption; B.2f materialization and CAS publication;
B.3 Threat mechanics-resource binding.

### README / CONTRIBUTING

State: `dungeonmind_dnd` now plans create-or-connect contributions against a
passed exact revision; still no repository access, no publication, no LLM, no
mechanics. CONTRIBUTING documents path-sensitive import allowlist for B.2d
planning modules only.

## §17 Work plan

1. **Re-anchor and audit** — confirm base commit; inspect open PRs; grep for
   overlapping contribution-planning work; record current import-boundary rules;
   confirm no kernel file needs modification.
2. **Add plan contracts** — enums, resolution/verification/relationship/blocker
   models, top-level plan with strict invariants and blocker correspondence.
3. **Add planning error** — `DndContributionPlanningError` with sanitization rules.
4. **Implement pure planner** — 13-step execution order; deterministic IDs;
   no repository imports; wrap parser failures safely.
5. **Add Gatewatch graph fixture** — minimal v3 world with North Gate and no
   Tripod/Breach objects.
6. **Add expected plan fixture** — byte-stable happy path with fixed actor/time.
7. **Add planning matrix tests** — happy path, identity, endpoints, relationships,
   integrity, determinism, replan stability.
8. **Add contract invariant tests** — resolution shapes, blocker correspondence,
   preview candidate-only rules, forbidden durable outcomes.
9. **Add sanitization tests** — sentinel strings absent from all error surfaces.
10. **Harden import boundaries** — path-sensitive allowlist; planning module
    infra/repo prohibition tests.
11. **Atomic documentation sync** — ADR-0006, architecture, authority, roadmap,
    README, contributing, handoff; verify all claims against implementation.

## §18 Verification commands

### Core gates

```bash
uv sync --locked
uv run ruff check .
uv run pyright
uv run --no-dev python -c "import dungeonmind"
uv run --no-dev python -c "import dungeonmind_dnd"
uv run pytest -m "not integration"
```

No PostgreSQL integration suite is required unless an implementation
unexpectedly touches integration paths — which is a stop condition.

### Focused tests

```bash
uv run pytest -q \
  tests/unit/test_dnd_threat_contribution_planning.py \
  tests/unit/test_dnd_threat_contribution_plan_contract.py \
  tests/unit/test_dnd_threat_contribution_plan_sanitization.py \
  tests/unit/test_import_boundaries.py
```

### Import proof

```bash
uv run --no-dev python - <<'PY'
import sys
import dungeonmind
assert "dungeonmind_dnd" not in sys.modules
print("kernel import remains profile-free")
PY

uv run --no-dev python - <<'PY'
import sys
import dungeonmind_dnd.application.contribution_planning
for forbidden in ("fastapi", "psycopg", "sqlalchemy", "openai", "anthropic"):
    assert forbidden not in sys.modules
print("planning import remains lightweight")
PY
```

### No-core-drift proof

```bash
git diff --name-only 685d0f0b5547171c27bcdcf7d9a7961a1e268674...HEAD \
  | rg '^src/dungeonmind/' && exit 1 || true

git diff -- uv.lock migrations src/dungeonmind
```

Expected: no changes under `src/dungeonmind/`, no lockfile change.

### Vocabulary and candidate immutability proof

```bash
git diff --name-only 685d0f0b5547171c27bcdcf7d9a7961a1e268674...HEAD \
  | rg '^src/dungeonmind_dnd/(profiles|vocabularies)/' && exit 1 || true

git diff --name-only 685d0f0b5547171c27bcdcf7d9a7961a1e268674...HEAD \
  | rg 'contracts/candidates\.py|contracts/vocabulary\.py|application/threat_candidates\.py' \
  && exit 1 || true
```

Expected: B.2c catalog, profile, and candidate modules byte-for-byte unchanged.

## §19 Acceptance rubric

### Boundary

- Base is PR #8 merge commit or an explicitly re-anchored descendant.
- No `src/dungeonmind/` file changed.
- Kernel never imports `dungeonmind_dnd`.
- B.2c modules retain narrow allowlist; only two planning modules use expanded allowlist.
- Planning modules never import repositories, infrastructure, service, or agents.
- Importing kernel or planning modules causes no network, config, provider, or database side effect.
- No dependency or lockfile change.

### Planner behavior

- Happy path matches expected plan fixture byte-for-byte.
- Exact replay is deterministic.
- Replan on newer base preserves proposed object IDs.
- Exact same-kind singleton → `resolved_existing`.
- No match → deterministic `provisional_new`.
- Ambiguity and cross-kind collision block whole plan.
- Explicit missing/wrong-kind endpoints block; never substituted.
- Duplicate packet triples and existing graph triples block.
- Integrity failures raise sanitized `DndContributionPlanningError`.
- No fuzzy, summary, or relationship-inferred matching.

### Contribution preview

- Present only on `ready_for_review`.
- Every assertion candidate/gm/asserted.
- No identity decisions, unresolved mentions, or diagnostics.
- Node assertions carry resolution outcome; relationship assertions do not.
- Ten assertions on happy path.

### Contracts

- Plan pins `expected_parent_revision_id == base_revision_id`.
- Blockers correspond bijectively to bad records.
- Plan records contain no prose fields.
- Durable identity outcomes rejected by contract validation.

### Fixtures and tests

- Gatewatch graph fixture is synthetic and license-safe.
- Expected plan fixture validates through strict models.
- Sanitization tests prove no sentinel leakage.
- Import-boundary tests prove path-sensitive allowlist.

### Documentation

- ADR-0006, architecture, authority, roadmap, README, contributing, and handoff agree.
- B.2c marked landed; B.2d described as planning-only.
- No doc claims publication, durable identity, fuzzy matching, or kernel changes.

## §20 Stop conditions

Stop and report before implementation or before broadening if any applies:

- main contains overlapping contribution-planning work.
- A core `src/dungeonmind/` change appears necessary.
- The planner requires repository fetch or current-head lookup.
- Scoped snapshot input cannot be forbidden structurally.
- Fuzzy or semantic matching is requested.
- Automatic merge of existing relationship triples is requested.
- Accepted assertions or durable identity records are requested in the preview.
- Vocabulary, profile, or candidate contracts must change.
- Graph schema beyond v3 must be supported in this PR.
- A new dependency is required.
- Fixtures require licensed rules text or sensitive campaign prose.
- Documentation cannot remain truthful without claiming publication or kernel D&D semantics.

Stop report format:

```text
Stop condition:
Discovered fact:
Affected invariant:
Paths/contracts involved:
Why B.2d cannot absorb it:
Smallest revised capability:
Safe work completed:
Work not attempted:
Operator decision required:
```

## §21 What remains false after merge

Even after successful B.2d:

- DungeonMind does not understand D&D terms at the kernel layer.
- No repository fetch occurs inside `dungeonmind_dnd`.
- No current-head lookup or stale-parent CAS check occurs in planning.
- Exact matching does not confirm identity — only proposes it.
- No `IdentityDecisionRecord` is created or persisted.
- No contribution is appended to any ledger.
- No graph revision is published.
- No fuzzy, semantic, embedding, or LLM matching exists.
- No relationship evidence augmentation or silent merge exists.
- No GM/player review UI exists.
- No product surface adopts the planner.
- No LLM extraction runtime exists.
- No statblock or mechanics binding exists.
- No generic interpretation layer exists.
- B.2c candidate validation behavior is unchanged.
- `dungeonmind_dnd` remains in the same distribution.
- Only one narrow D&D vocabulary and one Threat planning slice exist.

## §22 Named successors

### B.2e — Durable contribution review adoption

Independently useful outcome: `ready_for_review` B.2d plan → persist candidate
contribution and explicit reviewer identity outcomes → accept/reject individual
assertions → reload exact review state. Still no graph publication.

### B.2f — Accepted contribution materialization and expected-parent publication

Independently useful outcome: reviewed accepted contribution + expected parent →
deterministic graph payload → validation → atomic CAS publication →
revision-pinned receipt. Must handle stale parent without silently replanning.

### B.3 — Threat mechanics-resource binding

Independently useful outcome: approved Threat graph identity → exact external
statblock/mechanics resource ref → revision/digest pin → profile-owned hydration
contract. Mechanics stay outside the graph body. Only after a Threat identity
can be durably published.

Do not renumber external C/D/E/F lanes.

## §23 Required PR handback outline

The PR body must be the merge contract and include:

- **Exact state:** repository, branch, base SHA, head SHA, PR number, status,
  changed paths, paths outside allowlist.
- **Planning capability matrix:** function, inputs, outputs, mutating behavior
  (none), repository access (none).
- **Identity policy table:** normalization rule, four outcomes, cross-kind rule,
  provisional ID formula, replan stability rule.
- **Blocker code inventory:** all seven codes with trigger conditions.
- **Happy-path proof:** expected plan fixture match; resolution outcomes;
  verification state; relationship states; assertion counts; preview invariants.
- **Negative matrix:** each row from §13 with actual test name or result.
- **Sanitization proof:** sentinel absence from error surfaces.
- **Boundary proof:** no core changes; import tests; modules loaded after
  kernel/planning imports; B.2c artifact immutability.
- **Verification:** exact commands and actual results (sync; Ruff; Pyright;
  focused tests; full non-integration suite; import proof; no-core-drift proof; CI).
- **Documentation sync:** exact updates to ADR-0006, architecture, authority,
  roadmap, README, contributing, checked-in handoff.
- **Remaining false:** copy §21 and remove only statements actually made true.

## §24 Reviewer protocol / approval bar

Review this as a semantic-discipline and package-boundary PR, not as a
feature-completeness PR.

### Reconstruct intent

Before reading code, state: this PR makes validated D&D Threat candidates
graph-aware for review planning. It does not confirm identity, append
contributions, publish graphs, or make DungeonMind understand D&D at the kernel.

### Adversarial review cases

- Import `dungeonmind` → `dungeonmind_dnd` must not load.
- Import planning module → no repository, infra, DB, API, or config side effect.
- Inspect diff → no `src/dungeonmind/` changes.
- Inspect diff → no B.2c profile/vocabulary/candidate module changes.
- Run happy path → byte-match expected plan fixture.
- Add exact same-kind label match → `resolved_existing`, not `provisional_new`.
- Add two same-kind matches → `blocked`, no contribution.
- Add cross-kind exact match → `blocked_collision`, no contribution.
- Remove `obj:north-gate` from graph → `existing_object_missing`, no substitution.
- Point explicit endpoint at missing ID while similar label exists → still blocked.
- Duplicate packet triple → `duplicate_packet_relationship`.
- Pre-seed graph with same triple → `relationship_already_exists`.
- Submit typo label in graph → no fuzzy match; stays `provisional_new`.
- Inspect blocked plan → `proposed_contribution` is null.
- Inspect ready plan → all assertions candidate/gm/asserted; no identity decision IDs.
- Inspect error from malformed graph → no label/summary/locator leakage.
- Replan on newer base → same proposed object IDs, different plan/contribution IDs.
- Confirm `expected_parent_revision_id == base_revision_id`.

### Approval bar

Approve only when the reviewer can truthfully say:

> DungeonMindDnD can now plan exact-match create-or-connect Threat contributions
> against one passed immutable revision and emit a candidate-only review preview
> pinned to that parent — without repository access, durable identity decisions,
> fuzzy matching, or publication. The kernel remains unchanged and D&D-blind;
> every later step — review adoption, materialization, CAS publication, mechanics,
> and LLM extraction — remains a separate capability.

## §25 Opening directive

Start from merge commit `685d0f0b5547171c27bcdcf7d9a7961a1e268674`. Implement
exactly B.2d inside `src/dungeonmind_dnd`: add strict contribution-plan
contracts, add `DndContributionPlanningError`, add pure
`plan_threat_candidate_contribution` that reconciles one B.2c Threat packet
against one exact `dm_union_graph_v3` `StoredGraphRevision` using a
caller-supplied `GraphSnapshotReader`, verify explicit existing-object
references, perform exact label/alias create-or-connect blocking, plan
relationships with duplicate and existing-triple detection, emit machine-readable
blockers or a candidate-only `GraphContribution` preview, and pin
`expected_parent_revision_id` to the base revision. Prove the contract with
synthetic Gatewatch graph and Tripod Null-Calf fixtures including a byte-stable
expected plan. Update only import-boundary tests, package exports, and atomic
architecture/authority/roadmap/ADR/README/contributing/handoff documentation
outside the D&D package. Do not change any `src/dungeonmind/` file. Do not
modify B.2c profiles, vocabulary, or candidate modules. Do not fetch from
repositories, look up current head, fuzzy-match, create durable identity
decisions, append contributions, publish revisions, call an LLM, or add
mechanics/statblocks.
