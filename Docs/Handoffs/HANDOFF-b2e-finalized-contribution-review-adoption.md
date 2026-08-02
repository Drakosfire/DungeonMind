HANDOFF — B.2e Finalized Contribution Review Adoption

Created: 2026-08-01Status: ACTIVE — dispatch exactly one implementation capability.Canonical handoff path: Docs/Handoffs/HANDOFF-b2e-finalized-contribution-review-adoption.mdRepository: Drakosfire/DungeonMindSuggested branch: founding/pr-b2e-finalized-contribution-review-adoptionImplementation base: 1a4ee973725d51a188da1b1a7a67a987c85266fePredecessor: merged PR #9 — B.2d pinned Threat create-or-connect contribution planSuggested PR title: B.2e: finalized contribution review adoptionOne-line mission: Given one ready B.2d contribution plan, one complete set of GM assertion and identity verdicts, one exact confirmation receipt, and one matching confirm_commit capability policy, atomically persist a finalized, reloadable review state containing the superseded candidate contribution and its active reviewed successor—without graph materialization, graph-head publication, mutable draft review sessions, fuzzy identity work, or D&D semantics in the kernel.

§0 Capability decomposition decision

B.2d produces a fully content-bound but non-durable plan:

ready DndThreatContributionPlan
→ candidate-only GraphContribution preview
→ exact expected-parent pin
→ no repository write

The next architectural area contains several potentially separate outcomes:

Candidate outcome

Independently useful?

Public/durable contract changed?

User/operator surface changed?

Failure model changed?

Independently testable/revertible?

Decision

Convert a ready D&D plan into a generic review intent

Yes

Yes

No

Yes

Yes

Include — required predecessor seam

Require explicit GM confirm_commit authority and a content-bound confirmation receipt

Yes

Yes

No

Yes

Yes

Include — same durable-write invariant

Persist the original candidate contribution

No by itself

No new contribution schema

No

Yes

No

Include — one half of the review ledger

Persist accepted/rejected assertion verdicts

Yes

Yes

No

Yes

Yes

Include — core review outcome

Persist reviewer identity verdicts for each planned candidate

Yes

Yes

No

Yes

Yes

Include — required to make accepted node assertions interpretable

Emit and persist an active reviewed successor contribution

Yes

Uses existing contribution schema

No

Yes

Yes

Include — durable accepted/rejected contribution state

Reload and verify the exact finalized review state

Yes

Yes

No

Yes

Yes

Include — proves persistence is real

Mutable draft review sessions

Yes

Yes

Yes eventually

Yes

Yes

Successor

Incremental save/edit of individual decisions

Yes

Yes

Yes eventually

Yes

Yes

Successor

Review cancellation, retraction, or supersession

Yes

Yes

Yes eventually

Yes

Yes

Successor

Global IdentityDecisionRecord append

Yes

Yes

No

Yes

Yes

Successor with materialization

Accepted-assertion graph materialization

Yes

Yes

No

Yes

Yes

B.2f

Graph-head CAS publication

Yes

Existing graph contract

No

Yes

Yes

B.2f

Review API, CLI, tool, or UI

Yes

Yes

Yes

Yes

Yes

Successor

Relationship evidence augmentation

Yes

Yes

No

Yes

Yes

Reject for this lane

Human target override / merge / split

Yes

Yes

No

Yes

Yes

Successor identity-review capability

Selected capability: one-shot finalized contribution review adoption.

Why the included rows share one invariant:

An explicitly authorized and confirmed review of one exact ready plan is committed as one atomic, idempotent durable bundle, and the bundle can be reloaded without losing or reinterpreting any assertion verdict, identity verdict, source-plan pin, contribution payload, or reviewer authority fact.

The profile adapter, generic contracts, application service, persistence adapters, migration, and proof fixtures all establish this same invariant.

Why this is deliberately not a mutable review session

The repository has no review UI or API and no established mutable operation/session lifecycle for graph writes. Adding open drafts, incremental edits, cancellation, conflict resolution, and review replacement would create a second independently useful state machine. B.2e therefore accepts one complete verdict set and finalizes it atomically.

Named successors

B.2e.1 — mutable review workspace and review replacement
B.2f   — accepted contribution materialization + expected-parent CAS publication
B.3    — Threat mechanics-resource binding after published identity

§1 Mission

A trusted caller can finalize one complete GM review of a ready B.2d plan so
that the candidate contribution, reviewed successor, reviewer verdicts,
authority receipt, and expected-parent provenance survive exact reload as one
idempotent durable record.

Invariant

One review operation ID + one review-intent digest
→ exactly one atomic durable review bundle.

Exact replay
→ byte-equivalent reload.

Same operation ID or source plan with different review content
→ typed conflict and no partial write.

No B.2e path materializes graph objects, appends global identity decisions,
advances a graph head, or publishes a revision.

Mission falsification test

This is no longer one slice if implementation must also deliver:

an open/draft review lifecycle;

partial decision saves;

review replacement, cancellation, retraction, or supersession;

a review API, agent tool, CLI, or UI;

a new graph payload;

a PublishRevisionCommand;

global merge/split/alias identity operations;

reviewer-selected target overrides;

relationship evidence augmentation;

profile-specific interpretation in src/dungeonmind;

changes to B.2d planning semantics.

Stop rather than broadening.

§2 Context, authority, and boundaries

Field

Required content

Parent authority

Docs/Architecture/ARCHITECTURE.md; ADR-0001/0002/0004/0005/0006

Repository rules

CONTRIBUTING.md; import-boundary tests; locked dependencies; migration discipline

Base revision

1a4ee973725d51a188da1b1a7a67a987c85266fe

Predecessor contract

DndThreatContributionPlan / dmdnd_threat_contribution_plan_v1 from merged PR #9

Exact input consumed

One ready, fully validated B.2d plan translated into one generic review intent

Named successor

B.2f graph materialization and publication

What remains false

No graph revision, no head change, no global identity-decision ledger entry, no review surface

Explicit non-goals

Draft sessions, API/UI/tooling, target override, re-review, fuzzy matching, mechanics, LLM extraction

Repository-state gate

Before editing:

git fetch origin
git checkout main
git pull --ff-only
git rev-parse HEAD

Expected:

1a4ee973725d51a188da1b1a7a67a987c85266fe

This is the PR #9 merge commit.

If main moved, inspect every intervening change to:

src/dungeonmind/contracts/contribution.py
src/dungeonmind/contracts/identity.py
src/dungeonmind/contracts/capability.py
src/dungeonmind/application/repositories.py
src/dungeonmind/domain/capability.py
src/dungeonmind/infrastructure/memory/repositories.py
src/dungeonmind/infrastructure/postgres/records.py
src/dungeonmind_dnd/contracts/contribution_planning.py
src/dungeonmind_dnd/application/contribution_planning.py
migrations/versions/

Stop if another open or merged PR owns contribution review, confirmation receipts, review persistence, reviewed-contribution construction, or publication from B.2d plans.

Read in this order

Docs/Architecture/AUTHORITY.md

Docs/Architecture/ARCHITECTURE.md

Docs/Decisions/ADR-0001-postgresql-jsonb-pgvector.md

Docs/Decisions/ADR-0002-persistence-lifecycle-ownership.md

Docs/Decisions/ADR-0004-semantic-profile-boundary.md

Docs/Decisions/ADR-0005-dnd-profile-executable-boundary.md

Docs/Decisions/ADR-0006-pinned-profile-contribution-planning.md

Docs/Roadmaps/ROADMAP.md

Docs/Handoffs/HANDOFF-b2d-pinned-threat-contribution-plan.md

PR #9 final merge state

src/dungeonmind/contracts/contribution.py

src/dungeonmind/contracts/identity.py

src/dungeonmind/contracts/capability.py

src/dungeonmind/contracts/graph.py

src/dungeonmind/contracts/semantic_profile.py

src/dungeonmind/domain/capability.py

src/dungeonmind/domain/canonical.py

src/dungeonmind/domain/errors.py

src/dungeonmind/application/repositories.py

src/dungeonmind/infrastructure/memory/repositories.py

src/dungeonmind/infrastructure/postgres/records.py

src/dungeonmind/infrastructure/postgres/serialization.py

src/dungeonmind/infrastructure/postgres/evidence_extract.py

src/dungeonmind_dnd/contracts/contribution_planning.py

src/dungeonmind_dnd/application/contribution_planning.py

tests/fixtures/dungeonmind_dnd/tripod-null-calf-contribution-plan-v1.json

current migration head and repository conformance tests

tests/unit/test_import_boundaries.py

Authority precedence

1. Current checked-in DungeonMind contracts, ADRs, architecture, and migrations
2. Merged repository state at 1a4ee973...
3. This checked-in handoff
4. Existing implementation and tests
5. Project-source research and predecessor handoffs
6. Chat summaries

Existing-contract interpretation

Preserve these meanings:

GraphContribution remains the durable contribution ledger type.

Candidate assertions are proposals, not graph truth.

GraphContributionAssertion.acceptance_state remains the accepted/rejected review state.

ContributionRepository.append remains idempotent by contribution ID.

IdentityDecisionRecord remains the global graph-identity operation ledger.

CapabilityPolicy remains the sole authority for whether a commit effect is permitted.

PublishRevisionCommand remains the only normal graph-head publication command.

DndThreatContributionPlan remains profile-owned and non-durable.

no code under src/dungeonmind imports dungeonmind_dnd.

§3 Governing design decision

Selected flow

ready DndThreatContributionPlan
→ D&D profile adapter
→ generic ContributionReviewIntent
→ caller-issued CommitConfirmationReceipt
→ ContributionReviewSubmission
→ confirm_commit capability evaluation
→ current-head / exact-parent preflight
→ deterministic reviewed contribution
→ atomic review repository finalize
→ ContributionReviewState reload

Durable bundle

One finalized review atomically stores:

1. superseded candidate contribution
   - same contribution ID and assertion payload as B.2d preview
   - status = superseded
   - all assertions remain candidate

2. active reviewed successor contribution
   - source_kind = graph_review
   - supersedes candidate contribution
   - all assertions accepted or rejected
   - reviewer-confirmed final identity outcomes on node assertions

3. contribution review record
   - source-plan identity and digests
   - exact expected parent
   - complete assertion verdicts
   - complete candidate identity verdicts
   - reviewer identity and timestamp
   - operation and confirmation receipt identity
   - exact contribution digests

No intermediate active candidate row is exposed. The atomic repository receives the B.2d preview, deterministically constructs/stores the superseded candidate form and active reviewed successor in one transaction, then stores the review record.

Why the global identity-decision ledger is not written

The existing IdentityDecisionRecord contract describes graph identity operations such as alias add/remove, merge, split, unmerge, rejection, ambiguity, and human override. B.2e records reviewer verdicts over B.2d proposals:

confirm existing target
create proposed new target
reject candidate

Those verdicts are durable review facts but do not become graph identity operations until B.2f materializes accepted content against the expected parent. B.2e therefore:

persists identity verdicts inside the review record;

updates reviewed assertion identity_resolution_outcome;

leaves GraphContribution.identity_decision_ids empty;

appends no IdentityDecisionRecord.

B.2f may translate finalized verdicts into global identity-decision records while materializing and publishing. Do not force B.2e verdicts into mismatched merge/split/alias semantics.

Why candidate and reviewed contributions use separate IDs

The B.2d preview is content-bound and immutable as a proposal. Review changes acceptance and final identity outcomes. Mutating the same contribution payload would violate append idempotency. B.2e therefore stores:

candidate contribution ID
→ immutable proposal identity, stored superseded

reviewed contribution ID
→ deterministic successor, stored active

Assertion IDs remain unchanged across the two contributions so decisions refer to the same proposed claims.

§4 Observable-path inventory

Observable path

Current behavior

Required behavior

Same invariant?

Owning boundary

Build review intent from ready B.2d plan

No seam

Deterministic generic intent

Yes

D&D profile adapter

Blocked B.2d plan

Cannot persist

Adapter rejects

Yes

D&D profile adapter

Complete assertion verdict set

No contract

Exactly one accepted/rejected verdict per assertion

Yes

Review contract

Complete identity verdict set

No contract

Exactly one verdict per candidate resolution

Yes

Review contract

Commit authorization

Generic evaluator only

Exact confirm_commit policy + scope

Yes

Application service

Human confirmation

Mentioned but no receipt contract

Receipt bound to exact review intent

Yes

Review contract/service

Current-head preflight

B.2d only pins parent

Reject knowingly stale review

Yes

Application service

Candidate persistence

Preview only

Stored superseded

Yes

Review repository

Reviewed contribution persistence

Does not exist

Stored active successor

Yes

Review repository

Finalized review persistence

Does not exist

Stored once, idempotently

Yes

Review repository

Exact retry

No write

Same durable state

Yes

Repository

Same operation, different payload

No write

Typed idempotency conflict

Yes

Repository

Same source plan, second review

No rule

Typed already-finalized conflict

Yes

Repository

Partial DB failure

Not applicable

No candidate, successor, or review survives alone

Yes

PostgreSQL transaction

Reload exact review

Not possible

Reconstruct and cross-verify all three records

Yes

Repository/state contract

Graph head

Unchanged

Remains unchanged

Yes

Explicit negative proof

Identity decision rows

None

Remain none

Yes

Explicit negative proof

Review draft/edit

None

Still none

No

Successor

API/UI/tool

None

Still none

No

Successor

§5 Ownership and dependency boundary

DungeonMind kernel owns

generic review contracts
commit confirmation receipt
capability/scope enforcement
review application orchestration
durable contribution-review repository port
review persistence and migration
candidate/reviewed contribution lifecycle
idempotency and reconstruction
stale-parent preflight

DungeonMindDnD owns

translation from a valid ready DndThreatContributionPlan
to a generic ContributionReviewIntent

mapping:
  candidate resolution → generic identity proposal
  D&D plan pins → generic source-plan ref

It does not own persistence or reviewer authorization.

Dependency direction

Allowed:

dungeonmind_dnd.application.contribution_review
  → dungeonmind.contracts.contribution_review
  → existing kernel contracts/canonical helpers

dungeonmind.application.contribution_review
  → kernel contracts, domain capability evaluator, repository ports

infrastructure
  → application ports + contracts

Forbidden:

src/dungeonmind/*
  → dungeonmind_dnd

dungeonmind_dnd
  → dungeonmind.application.repositories
  → dungeonmind.infrastructure
  → dungeonmind.service
  → database drivers

Import-boundary update

Only the new D&D adapter may add:

dungeonmind.contracts.contribution_review

to the profile-package allowlist.

The B.2c and B.2d modules retain their existing exact allowlists.

§6 New generic contracts

Create:

src/dungeonmind/contracts/contribution_review.py

All contracts inherit DungeonMindModel, use extra="forbid" through the existing base, and are versioned.

§6.1 Schema versions

dm_contribution_plan_ref_v1
dm_contribution_identity_proposal_v1
dm_contribution_identity_verdict_v1
dm_contribution_assertion_verdict_v1
dm_contribution_review_intent_v1
dm_commit_confirmation_receipt_v1
dm_contribution_review_submission_v1
dm_contribution_review_record_v1
dm_contribution_review_state_v1

§6.2 ID and digest shapes

operation_id     reviewop:<32 lowercase hex>
review_id        review:<32 lowercase hex>
confirmation_id  confirm:<32 lowercase hex>
contribution_id  existing GraphContribution ID convention
digest           exactly 64 lowercase hex

§6.3 ContributionPlanRef

Fields:

schema_version
source_plan_schema
source_plan_id
source_plan_sha256
source_input_sha256
preview_content_sha256
candidate_contribution_sha256
expected_parent_revision_id
base_graph_schema
base_graph_payload_sha256
semantic_profile

Rules:

all IDs nonblank;

all digests exact lowercase SHA-256;

semantic_profile is the generic kernel SemanticProfileRef;

no path, module name, URI, prompt, label, summary, evidence locator, or raw plan payload;

this is an opaque provenance pin, not a profile interpreter.

For B.2d:

source_plan_schema = dmdnd_threat_contribution_plan_v1
source_plan_id = plan.plan_id
source_plan_sha256 = canonical SHA-256 of the complete serialized plan
source_input_sha256 = plan.candidate_packet_sha256
preview_content_sha256 = plan.preview_content_sha256
candidate_contribution_sha256 = canonical SHA-256 of plan.proposed_contribution
expected_parent_revision_id = plan.expected_parent_revision_id
base_graph_schema = plan.base_graph_schema
base_graph_payload_sha256 = plan.base_graph_payload_sha256
semantic_profile = plan.semantic_profile

§6.4 ContributionIdentityProposal

Fields:

schema_version
candidate_id
candidate_kind
planned_outcome
target_object_id
matched_object_ids

Allowed planned_outcome:

resolved_existing
provisional_new

Rules:

one proposal per B.2d candidate resolution;

candidate IDs unique and deterministically sorted;

target object IDs unique across proposals;

resolved_existing requires exactly one matched object equal to target;

provisional_new requires no matched objects;

no labels, aliases, summaries, confidence, or evidence prose.

§6.5 ContributionIdentityVerdictKind

confirm_existing
create_new
reject_candidate

§6.6 ContributionIdentityVerdict

Fields:

schema_version
candidate_id
verdict
target_object_id

Rules:

one verdict per proposal;

target must exactly equal the proposal target;

confirm_existing allowed only for resolved_existing;

create_new allowed only for provisional_new;

reject_candidate allowed for either;

no target override in v1.

§6.7 ContributionAssertionVerdict

Fields:

schema_version
assertion_id
acceptance_state

Rules:

acceptance_state is exactly accepted or rejected;

candidate is forbidden;

one verdict per candidate contribution assertion;

assertion IDs unique and deterministically sorted.

§6.8 ContributionReviewIntent

Fields:

schema_version
operation_id
world_id
campaign_id
plan_ref
candidate_contribution
identity_proposals
identity_verdicts
assertion_verdicts
reviewer_id
reviewed_at
review_intent_sha256

Canonical intent material excludes only review_intent_sha256 itself.

Rules:

review_intent_sha256 must equal the canonical digest of every other field;

candidate contribution digest must equal plan_ref.candidate_contribution_sha256;

contribution world/campaign must equal intent;

candidate contribution must be:

source_kind=extraction;

status=active;

no supersession;

all assertions candidate, gm, asserted;

every assertion evidence-bearing;

empty identity_decision_ids, unresolved_mentions, and diagnostics;

identity proposals and verdicts form an exact one-to-one mapping;

assertion verdicts cover every candidate assertion exactly once;

every node assertion subject maps to one identity proposal target;

relationship endpoints may also reference explicit existing objects not present in proposals;

no assertion content is copied into the verdict records.

§6.9 CommitConfirmationReceipt

Fields:

schema_version
confirmation_id
operation_id
review_intent_sha256
actor
tool_name
effect
world_id
campaign_id
expected_parent_revision_id
confirmed_at

Exact literals:

tool_name = dungeonmind.finalize_contribution_review
effect = commit

Rules:

receipt operation/digest/actor/scope/parent/time exactly match the intent;

confirmed_at == reviewed_at;

deterministic ID:confirm:<hash(operation_id, review_intent_sha256, actor, confirmed_at)>;

receipt is an explicit confirmation fact, not authentication;

caller authentication remains an outer trusted-boundary responsibility.

§6.10 ContributionReviewSubmission

Fields:

schema_version
intent
confirmation

The model validator requires exact receipt-to-intent binding.

§6.11 ContributionReviewRecord

Fields:

schema_version
review_id
operation_id
world_id
campaign_id
plan_ref
review_intent_sha256
candidate_preview_sha256
stored_candidate_contribution_id
stored_candidate_sha256
reviewed_contribution_id
reviewed_contribution_sha256
identity_proposals
identity_verdicts
assertion_verdicts
reviewer_id
reviewed_at
confirmation_id
status

Exact status:

finalized

Rules:

deterministic review_id;

candidate preview digest equals plan ref candidate digest;

operation, plan, decisions, reviewer, time, and receipt identities preserved exactly;

no free-form review prose;

no graph revision result;

no global identity-decision IDs;

no publication receipt.

§6.12 ContributionReviewState

Fields:

schema_version
record
candidate_contribution
reviewed_contribution

Cross-record rules:

candidate ID equals record;

candidate status is superseded;

candidate assertions remain candidate;

candidate payload differs from B.2d preview only in permitted lifecycle fields:

status active → superseded;

reviewed ID equals record;

reviewed status is active;

reviewed source kind is graph_review;

reviewed contribution supersedes candidate ID;

candidate/reviewed world, campaign, source anchors, extraction profile, and assertion identities agree;

record digests match both contributions;

reviewed assertion content/evidence/IDs equal candidate assertion content/evidence/IDs;

only acceptance state and node identity outcome may differ;

every assertion is accepted or rejected;

reviewed contribution has no unresolved mentions, diagnostics, or global identity-decision IDs;

reviewed author and timestamp equal reviewer/review time.

§7 Deterministic review identity

Review-intent digest

Canonical material:

{
  "schema": "dm_contribution_review_intent_v1",
  "operation_id": "...",
  "world_id": "...",
  "campaign_id": "...",
  "plan_ref": {...},
  "candidate_contribution": {...},
  "identity_proposals": [...],
  "identity_verdicts": [...],
  "assertion_verdicts": [...],
  "reviewer_id": "...",
  "reviewed_at": "..."
}

All lists are deterministically sorted before hashing.

Review ID

review:<32 lowercase hex>

Material:

{
  "schema": "dm_contribution_review_id_v1",
  "operation_id": "...",
  "review_intent_sha256": "...",
  "world_id": "..."
}

Reviewed contribution ID

contrib:<32 lowercase hex>

Material:

{
  "schema": "dm_reviewed_contribution_id_v1",
  "review_id": "...",
  "candidate_contribution_id": "..."
}

Exact replay

The caller must reuse:

operation_id
reviewer_id
reviewed_at
all verdicts
confirmation receipt

Same complete submission produces the same:

review_intent_sha256
review_id
reviewed_contribution_id
record payload

Changing any field while reusing the operation ID is an idempotency conflict.

One finalized review per source plan

Database and in-memory adapters enforce unique:

(world_id, source_plan_id)

A second operation for the same plan is rejected with a typed already-finalized error. B.2e has no re-review or supersession semantics.

A corrected review requires a newly generated B.2d plan with a new plan ID. A future review-replacement capability may introduce explicit supersession.

§8 Profile-side adapter

Create:

src/dungeonmind_dnd/application/contribution_review.py

Public function:

def build_threat_contribution_review_intent(
    plan: DndThreatContributionPlan,
    *,
    operation_id: str,
    assertion_verdicts: Mapping[str, AcceptanceState],
    identity_verdicts: Mapping[str, ContributionIdentityVerdictKind],
    reviewer_id: str,
    reviewed_at: datetime,
) -> ContributionReviewIntent:
    ...

Adapter responsibilities

Require a validated ready_for_review plan.

Require non-null preview_content_sha256.

Require non-null proposed_contribution.

Canonically hash the complete plan.

Build ContributionPlanRef.

Translate every candidate resolution into one generic identity proposal.

Convert caller verdict mappings into sorted generic verdict records.

Preserve the exact candidate contribution preview.

Build and validate the generic intent.

Return no receipt and perform no write.

Adapter rejection

Reject through a sanitized D&D-owned typed error when:

plan is blocked;

plan lacks a preview;

plan fails re-validation;

plan digest/content binding is invalid;

verdict coverage is incomplete;

an identity verdict is incompatible with the planned outcome;

assertion IDs or candidate IDs are unknown.

Do not echo labels, summaries, aliases, or evidence locators in errors.

Explicit boundary

The kernel service accepts only the generic intent/submission. It never imports or parses DndThreatContributionPlan.

§9 Review decision semantics

§9.1 Assertion completeness

Every candidate assertion receives exactly one final state:

accepted
rejected

No candidate state survives in the reviewed successor.

§9.2 Identity completeness

Every candidate resolution receives exactly one verdict.

Planned outcome

Allowed final verdicts

Reviewed node outcome

resolved_existing

confirm_existing, reject_candidate

resolved_existing or rejected

provisional_new

create_new, reject_candidate

created_new or rejected

§9.3 Rejected candidate closure

When a candidate is reject_candidate, every assertion involving its target must be rejected:

node label/alias/summary whose subject == target
relationship whose subject == target
relationship whose object == target

This includes relationships to explicit existing objects.

§9.4 Confirmed new candidate

create_new requires:

exactly one label assertion for the target;

that label assertion is accepted;

no accepted assertion targets the same object under another candidate proposal.

Other aliases, summary, and relationships may be independently accepted or rejected.

§9.5 Confirmed existing candidate

confirm_existing permits independent acceptance/rejection of label, alias, summary, and relationship assertions. Identity confirmation does not force every proposed field to be accepted.

§9.6 Relationship acceptance

A relationship assertion may be accepted only when every endpoint corresponding to a candidate proposal has a non-rejection identity verdict.

Explicit existing endpoints from B.2d do not require a B.2e identity verdict; B.2d already verified them against the exact parent.

§9.7 No target override

The reviewer cannot redirect a candidate to a different object in B.2e. Any target disagreement requires:

new B.2d plan
or future human-override/merge capability

Do not encode override in free-form diagnostics.

§10 Reviewed contribution construction

Application service constructs two stored contribution payloads.

§10.1 Superseded candidate contribution

Start with the exact B.2d preview.

Change only:

status: active → superseded

Preserve:

contribution_id
source_kind = extraction
all assertion IDs/content/evidence
all assertion acceptance_state = candidate
all planned identity outcomes
authored_by
produced_at
source anchors
campaign
extraction profile
empty decisions/unresolved/diagnostics

§10.2 Active reviewed successor contribution

Construct:

GraphContribution(
    contribution_id=<derived>,
    world_id=<same>,
    source_kind=ContributionSourceKind.GRAPH_REVIEW,
    source_artifact_id=<same>,
    source_revision_id=<same>,
    extraction_profile=<same>,
    produced_at=reviewed_at,
    campaign_scope=<same>,
    status=ContributionStatus.ACTIVE,
    supersedes_contribution_id=<candidate id>,
    assertions=<same assertions with final verdict fields>,
    unresolved_mentions=[],
    identity_decision_ids=[],
    authored_by=reviewer_id,
    diagnostics={},
)

Assertion transformation

Preserve byte-equivalent values for:

assertion_id
assertion_kind
subject_object_id
object_object_id
predicate
label
value
evidence_refs
source_artifact_id
source_revision_id
campaign_scope
temporal_scope
visibility
epistemic_kind

Change:

acceptance_state
node identity_resolution_outcome

Relationship assertions retain:

identity_resolution_outcome = null

No new assertion is invented; none is removed.

All-rejected review

Allowed.

The reviewed successor may contain only rejected assertions. It remains an active durable review result but creates no graph truth. B.2f must treat zero accepted assertions explicitly and must not publish a meaningless revision silently.

§11 Application service

Create:

src/dungeonmind/application/contribution_review.py

Constants:

FINALIZE_REVIEW_TOOL = dungeonmind.finalize_contribution_review

Public function:

def finalize_contribution_review(
    submission: ContributionReviewSubmission,
    *,
    capability_policy: CapabilityPolicy,
    world_graph_repository: WorldGraphRepository,
    review_repository: ContributionReviewRepository,
) -> ContributionReviewState:
    ...

Optional thin read helper:

def load_contribution_review(
    world_id: str,
    review_id: str,
    *,
    review_repository: ContributionReviewRepository,
) -> ContributionReviewState | None:
    ...

Required execution order

1. validate submission
2. evaluate capability:
     tool = dungeonmind.finalize_contribution_review
     effect = commit
3. require policy graph scope
4. require GM admissibility
5. require exact world/campaign scope match
6. require explicit revision_pin == expected_parent
7. verify confirmation receipt binding
8. read current graph head
9. require current head == expected parent
10. read exact expected-parent revision
11. verify graph schema and payload digest against plan ref
12. validate review-decision closure
13. derive review ID
14. derive superseded candidate contribution
15. derive active reviewed successor
16. build review record and state
17. repository.finalize(state)
18. return exact stored/reconstructed state

Capability rules

evaluate_capability must pass with:

category = confirm_commit
allowed effect includes commit
tool enabled = dungeonmind.finalize_contribution_review
graph scope present

Additional exact checks:

policy.graph_scope.world_id == intent.world_id
policy.graph_scope.campaign_id == intent.campaign_id
policy.graph_scope.admissibility == gm
policy.graph_scope.revision_pin == plan_ref.expected_parent_revision_id

A missing revision pin is denial. B.2e never resolves a moving head from an unpinned commit policy.

Current-head preflight

B.2e rejects a plan already stale at review time:

head_revision_id != expected_parent_revision_id
→ StaleParentRevisionError
→ no durable review write

This is not publication CAS. The head may advance immediately after review commit. B.2f must still perform atomic expected-parent CAS and must never assume B.2e's preflight is sufficient.

Exact revision verification

The expected-parent revision must exist and match:

world_id
revision_id
graph_schema
graph_payload_sha256

No need to interpret D&D terms; B.2d already validated profile semantics.

§12 Repository port and atomicity

Modify:

src/dungeonmind/application/repositories.py

Add:

class ContributionReviewRepository(Protocol):
    def finalize(
        self,
        state: ContributionReviewState,
    ) -> ContributionReviewState:
        ...

    def get(
        self,
        world_id: str,
        review_id: str,
    ) -> ContributionReviewState | None:
        ...

    def get_for_plan(
        self,
        world_id: str,
        source_plan_id: str,
    ) -> ContributionReviewState | None:
        ...

Port guarantees

finalize atomically persists:

superseded candidate contribution
active reviewed contribution
review record
all evidence refs referenced by both contributions

All or nothing.

Idempotency

Exact existing review state:

same operation ID
same source plan
same review record fingerprint
same candidate fingerprint
same reviewed fingerprint
→ return exact reconstructed state

Conflicts:

same operation ID, different payload
→ IdempotencyConflictError

same source plan, different operation/review
→ ContributionReviewAlreadyFinalizedError

same candidate or reviewed contribution ID, different payload
→ IdempotencyConflictError

Reconstruction

Every read:

reconstructs the review record;

loads both contribution rows;

verifies row identity/fingerprint integrity;

builds ContributionReviewState;

re-runs all cross-record validators.

Missing or drifted child records raise PersistenceIntegrityError, not None.

Unknown review ID returns None.

§13 In-memory adapter

Modify:

src/dungeonmind/infrastructure/memory/repositories.py
src/dungeonmind/infrastructure/memory/__init__.py

Add:

InMemoryContributionReviewRepository

Shared-state requirement

The review repository and ordinary contribution repository must read the same contribution dictionary.

Expected construction:

contributions = InMemoryContributionRepository()
reviews = InMemoryContributionReviewRepository(contributions)

Refactor private in-memory contribution state as needed so:

one re-entrant lock protects candidate contribution, reviewed contribution, and review record;

finalize preflights every conflict before inserting anything;

injected failure proves no partial write;

ordinary ContributionRepository.get/list_for_world sees both stored contributions.

Do not expose adapter storage types through application ports.

§14 PostgreSQL adapter and migration

Modify:

src/dungeonmind/infrastructure/postgres/records.py
src/dungeonmind/infrastructure/postgres/__init__.py

Add:

PostgresContributionReviewRepository
PostgresRepositoryBundle.contribution_reviews

Internal contribution insert helper

Refactor existing contribution insertion into a transaction-local private helper so:

normal PostgresContributionRepository.append behavior remains unchanged;

review finalize can insert/reconcile two contributions inside the same transaction;

evidence refs are upserted inside that transaction;

no nested independent transaction is opened.

New table

Create exactly one Alembic migration adding:

dungeonmind.contribution_reviews

Columns:

world_id                     text not null
review_id                    text not null
operation_id                 text not null
source_plan_id               text not null
candidate_contribution_id    text not null
reviewed_contribution_id     text not null
expected_parent_revision_id  text not null
reviewer_id                  text not null
reviewed_at                  timestamptz not null
status                       text not null
schema_version               text not null
record_fingerprint           text not null
payload                      jsonb not null

Constraints:

primary key (world_id, review_id)
unique (world_id, operation_id)
unique (world_id, source_plan_id)

foreign key (world_id, candidate_contribution_id)
  → graph_contributions(world_id, contribution_id)

foreign key (world_id, reviewed_contribution_id)
  → graph_contributions(world_id, contribution_id)

foreign key (world_id, expected_parent_revision_id)
  → graph_revisions(world_id, revision_id)

check status = 'finalized'

Use the repository's current schema, naming, timestamp, JSONB, and downgrade conventions.

Transaction order

Inside one transaction:

1. ensure world/campaign as existing contribution logic requires
2. preflight existing review by operation ID
3. preflight existing review by source plan ID
4. preflight both contribution IDs/fingerprints
5. upsert all evidence refs
6. insert/reconcile superseded candidate contribution
7. insert/reconcile active reviewed contribution
8. insert review row
9. re-read and reconstruct complete state
10. commit

Any failure rolls back all inserts.

Migration bounded discovery exception

The exact migration filename depends on the current Alembic head.

Directory: migrations/versions/
Maximum additional paths: 1
Allowed path kind: one new Alembic revision
Decision rule: revision must descend from the single current head and add only contribution_reviews
Required report: filename, revision ID, down_revision, upgrade/downgrade objects

No existing migration may be edited.

§15 Failure model and sanitization

Add to:

src/dungeonmind/domain/errors.py

New errors

ContributionReviewValidationError
  code = contribution_review_validation_error

ContributionReviewAlreadyFinalizedError
  code = contribution_review_already_finalized

Reuse:

CapabilityDeniedError
StaleParentRevisionError
RevisionNotFoundError
IdempotencyConflictError
PersistenceIntegrityError
PersistenceUnavailableError

Error classification

Validation error:

incomplete verdict coverage;

incompatible identity verdict;

rejected-candidate closure violation;

accepted relationship with rejected candidate endpoint;

create-new without accepted label;

receipt mismatch;

intent digest mismatch;

candidate contribution shape mismatch.

Capability denial:

wrong tool/effect/category;

disabled tool;

missing scope;

player admissibility;

world/campaign/revision mismatch.

Stale parent:

current head differs before review commit.

Already finalized:

another finalized review exists for the same source plan.

Idempotency conflict:

operation/contribution/review ID replayed with different bytes.

Persistence integrity:

stored record/contribution/fingerprint/cross-link drift.

Sanitization

Errors may include:

operation ID
review ID
source plan ID
contribution IDs
assertion IDs
candidate IDs
object IDs
revision IDs
schema IDs
digests
machine-readable reason codes

Errors must not include:

labels
aliases
summaries
evidence locators or URIs
source prose
raw plan payload
raw contribution payload
database DSN
filesystem paths
confirmation secrets

No confirmation secret exists in v1; the receipt is an audit binding, not a bearer credential.

§16 Synthetic proof fixtures

Reuse unchanged

tests/fixtures/dungeonmind_dnd/tripod-null-calf-contribution-plan-v1.json
tests/fixtures/dungeonmind_dnd/tripod-null-calf-threat-candidates-v1.json
tests/fixtures/dungeonmind_dnd/gatewatch-world-graph-v3.json

Their bytes and digests must not change.

Create review-intent fixture

tests/fixtures/dungeonmind_dnd/tripod-null-calf-review-intent-v1.json

Fixed inputs:

operation_id = reviewop:11111111111111111111111111111111
reviewer_id = operator:synthetic-gm
reviewed_at = 2026-08-01T22:00:00Z

Identity verdicts:

cand:tripod-null-calf   → create_new
cand:north-gate-breach  → create_new

Assertion verdict set must be mixed, not all accepted, so per-assertion review is proven.

Recommended exact distribution for the current ten assertions:

accepted: 8
rejected: 2

Both candidate label assertions must be accepted. All three relationships may be accepted. Reject two non-label node-field assertions.

Create confirmation receipt fixture

tests/fixtures/contribution_reviews/tripod-null-calf-confirmation-v1.json

It binds the exact intent digest, reviewer, operation, parent, and timestamp.

Create expected review-state fixture

tests/fixtures/contribution_reviews/tripod-null-calf-finalized-review-state-v1.json

It contains:

finalized record;

superseded candidate contribution;

active reviewed successor;

exact deterministic IDs/digests;

eight accepted and two rejected reviewed assertions;

both provisional candidates promoted to created_new on node assertions;

relationship identity outcomes null;

no global identity-decision IDs;

no graph revision or publication receipt.

§17 Deterministic proof matrix

Happy path

Case

Expected

Ready B.2d plan + complete verdicts

Valid review intent

Matching confirmation + confirm_commit GM policy

Finalized durable review

Reload by review ID

Byte-equivalent expected fixture

Reload by source plan ID

Same state

Ordinary contribution read

Candidate superseded; reviewed active

Exact operation replay

Same state, no duplicates

Review commit

Graph head unchanged

Review commit

Identity-decision repository unchanged

Plan adapter

Case

Expected

Blocked plan

Adapter rejects

Ready plan missing preview digest

Adapter rejects

Ready plan missing contribution

Adapter rejects

Unknown assertion verdict ID

Reject

Missing assertion verdict

Reject

Unknown candidate verdict ID

Reject

Missing candidate verdict

Reject

Confirm-existing on provisional proposal

Reject

Create-new on resolved-existing proposal

Reject

Assertion/identity closure

Case

Expected

Every assertion decided

Valid

One assertion remains candidate

Reject

Rejected candidate with accepted label

Reject

Rejected candidate with accepted relationship

Reject

Create-new with rejected label

Reject

Confirm-existing with independently rejected alias

Valid

Accepted relationship with both candidates confirmed

Valid

All assertions rejected

Valid finalized review

Authority

Case

Expected

Confirm-commit GM policy, exact scope

Allowed

Read-only policy

CapabilityDeniedError

Preview-write policy

CapabilityDeniedError

Tool disabled

CapabilityDeniedError

Player admissibility

CapabilityDeniedError

Wrong world

CapabilityDeniedError

Wrong campaign

CapabilityDeniedError

Missing revision pin

CapabilityDeniedError

Wrong revision pin

CapabilityDeniedError

Receipt digest mismatch

Review validation error

Receipt actor mismatch

Review validation error

Receipt timestamp mismatch

Review validation error

Graph preflight

Case

Expected

Current head equals expected parent

Proceed

Current head advanced

StaleParentRevisionError

Expected revision missing

RevisionNotFoundError

Revision payload digest differs

Review validation/integrity error

Graph schema differs from plan ref

Review validation/integrity error

Head changes after commit

Review remains durable; B.2f must later fail CAS

Persistence/idempotency

Case

Expected

Same operation and bytes

Exact replay

Same operation, changed verdict

IdempotencyConflictError

Different operation, same source plan

AlreadyFinalizedError

Existing candidate ID with different payload

IdempotencyConflictError

Existing reviewed ID with different payload

IdempotencyConflictError

Failure after first contribution insert

Full rollback

Failure before review row insert

Full rollback

Missing candidate row on reload

PersistenceIntegrityError

Tampered reviewed row

PersistenceIntegrityError

Tampered review row identity column

PersistenceIntegrityError

Negative capability proof

After success:

world_graph_head unchanged
graph revision count unchanged
identity decision count unchanged
no PublishRevisionCommand constructed
no D&D import under src/dungeonmind

§18 Import-boundary evolution

Modify:

tests/unit/test_import_boundaries.py

Kernel rule remains absolute

src/dungeonmind never imports dungeonmind_dnd

D&D adapter allowance

Only:

dungeonmind_dnd.application.contribution_review

may additionally import:

dungeonmind.contracts.contribution_review
dungeonmind.contracts.contribution
dungeonmind.contracts.identity
dungeonmind.contracts.semantic_profile
dungeonmind.domain.canonical

Still forbidden from profile package:

dungeonmind.application.repositories
dungeonmind.application.contribution_review
dungeonmind.infrastructure
dungeonmind.service
dungeonmind.agents
psycopg
fastapi
provider SDKs

Runtime import proof:

uv run --no-dev python - <<'PY'
import sys
import dungeonmind_dnd.application.contribution_review

for forbidden in (
    "fastapi",
    "psycopg",
    "sqlalchemy",
    "openai",
    "anthropic",
):
    assert forbidden not in sys.modules
PY

§19 Files in scope — exact allowlist

Action

Path

Purpose

Create

Docs/Handoffs/HANDOFF-b2e-finalized-contribution-review-adoption.md

Canonical implementation handoff

Create

Docs/Decisions/ADR-0007-finalized-contribution-review-adoption.md

Durable review/confirmation/atomicity decision

Modify

Docs/Decisions/ADR-0006-pinned-profile-contribution-planning.md

Add “extended by ADR-0007” note only

Modify

Docs/Architecture/ARCHITECTURE.md

Add kernel-side finalized review layer

Modify

Docs/Architecture/AUTHORITY.md

Review authority and non-canon rules

Modify

Docs/Roadmaps/ROADMAP.md

Mark B.2d landed; make B.2e current

Modify

README.md

Truthful current capability boundary

Modify

CONTRIBUTING.md

Review write/receipt/idempotency rules

Modify

src/dungeonmind/contracts/__init__.py

Export review contracts if package convention does so

Create

src/dungeonmind/contracts/contribution_review.py

Generic review wire contracts

Modify

src/dungeonmind/domain/errors.py

Review errors

Create

src/dungeonmind/application/contribution_review.py

Authority/preflight/review orchestration

Modify

src/dungeonmind/application/repositories.py

Review repository port

Modify

src/dungeonmind/infrastructure/memory/repositories.py

Atomic in-memory review repository

Modify

src/dungeonmind/infrastructure/memory/__init__.py

Export in-memory review repository

Modify

src/dungeonmind/infrastructure/postgres/records.py

Atomic PostgreSQL review repository

Modify

src/dungeonmind/infrastructure/postgres/__init__.py

Export/wire PostgreSQL review repository

Create

src/dungeonmind_dnd/application/contribution_review.py

Ready-plan → generic review-intent adapter

Modify

src/dungeonmind_dnd/application/__init__.py

Export adapter

Create

tests/fixtures/dungeonmind_dnd/tripod-null-calf-review-intent-v1.json

Deterministic adapter output

Create

tests/fixtures/contribution_reviews/tripod-null-calf-confirmation-v1.json

Confirmation binding fixture

Create

tests/fixtures/contribution_reviews/tripod-null-calf-finalized-review-state-v1.json

Exact durable state fixture

Create

tests/unit/test_contribution_review_contract.py

Contract/cross-record invariants

Create

tests/unit/test_contribution_review_service.py

Authority, preflight, construction, negatives

Create

tests/unit/test_contribution_review_memory_repository.py

Atomic/idempotent in-memory persistence

Create

tests/unit/test_dnd_threat_contribution_review_adapter.py

Profile seam proof

Create

tests/integration/test_postgres_contribution_review_repository.py

PostgreSQL transaction/reload proof

Modify

tests/unit/test_import_boundaries.py

Exact path-sensitive allowance

Create

migrations/versions/<next>_contribution_reviews.py

One new review table; bounded filename discovery

Conditional path

pyproject.toml may be modified only if a newly created package directory under tests/fixtures requires explicit packaging—which it should not. No new dependency is allowed.

Hard forbidden paths

No changes under:

src/dungeonmind/contracts/contribution.py
src/dungeonmind/contracts/identity.py
src/dungeonmind/contracts/graph.py
src/dungeonmind/application/graph_snapshot.py
src/dungeonmind/infrastructure/postgres/graph.py
src/dungeonmind/service/
src/dungeonmind/agents/
src/dungeonmind_dnd/contracts/
src/dungeonmind_dnd/profiles/
src/dungeonmind_dnd/vocabularies/
tests/fixtures/dungeonmind_dnd/tripod-null-calf-contribution-plan-v1.json
tests/fixtures/dungeonmind_dnd/tripod-null-calf-threat-candidates-v1.json
tests/fixtures/dungeonmind_dnd/gatewatch-world-graph-v3.json
uv.lock
compose.postgres.yml

No existing migration may change.

If existing contribution or identity contracts must change, stop.

§20 Atomic documentation sync

Documentation is merge-blocking.

§20.1 ADR-0007

Record:

B.2e is a one-shot finalized review, not a draft session.

Kernel receives a generic intent; it never imports D&D plan contracts.

D&D adapter translates and validates the ready plan.

Durable commit requires exact confirm_commit capability and GM scope.

A confirmation receipt binds the exact intent, reviewer, parent, and time.

Current head must equal expected parent at review preflight.

B.2f must still perform publication CAS.

Candidate proposal is stored superseded.

Reviewed successor is stored active with accepted/rejected assertions.

Assertion IDs/content/evidence remain unchanged.

Reviewer identity verdicts are durable review facts.

No global IdentityDecisionRecord is appended.

Review repository atomically stores both contributions and the review row.

One operation/source plan finalizes once.

No review replacement/cancellation exists.

Review state is durable but not graph canon.

No graph revision or head mutation occurs.

Rejected alternatives:

mutate candidate contribution in place;

store verdicts only in diagnostics;

append identity verdicts as fake merge/alias decisions;

let profile package access repositories;

review without confirmation receipt;

unpinned commit policy;

allow player-scoped review;

allow partial decision coverage;

build draft session lifecycle;

publish in the same PR.

§20.2 Architecture

Add:

Kernel-side finalized review layer (B.2e)
  generic review intent
  + confirm_commit policy
  + confirmation receipt
  + current expected parent
  → atomic superseded candidate contribution
  → active reviewed successor contribution
  → finalized contribution review record

  no graph materialization
  no graph publication
  no global identity decision append
  no mutable review workspace

Clarify:

profile semantics end at intent construction;

review verdicts are durable governance state, not graph truth;

accepted assertions become publication-eligible only;

B.2f owns graph payload construction and CAS.

§20.3 Authority

Add:

source plan ref/digest is authority for what was reviewed;

candidate contribution is authority for proposed claim bytes;

assertion verdicts are authority for accepted/rejected review state;

identity verdicts are authority for reviewer disposition of planned targets;

confirmation receipt + capability policy are authority for commit permission;

expected parent is authority for review context;

finalized review is not canonical graph truth;

published graph revision remains final graph authority.

§20.4 Roadmap

B.2b  semantic profile boundary ✅
B.2c  Threat vocabulary and candidates ✅
B.2d  pinned create-or-connect plan ✅
B.2e  finalized contribution review adoption ← current
B.2f  accepted materialization + CAS publication

B.2e outcome:

ready B.2d plan
+ complete GM verdicts
+ confirm_commit receipt
→ atomic durable review bundle
→ exact reload
→ no publication

§20.5 README

State:

B.2d landed;

B.2e persists one finalized review;

review requires explicit confirmation and GM commit policy;

candidate and reviewed contributions are durable;

graph head remains unchanged;

no review UI/API or publication exists.

§20.6 CONTRIBUTING

Add hard rules:

Durable review writes require confirm_commit capability and an exact receipt.
Review policy must be GM, world/campaign exact, and revision-pinned.
Never mutate a candidate contribution's assertion payload in place.
Final review produces a successor contribution.
Every assertion and candidate proposal must receive a complete verdict.
Profile packages may build generic intents but may not access repositories.
Review persistence must be atomic across review + both contributions.
A finalized review is publication-eligible input, not graph truth.

§21 Work plan

Step 1 — Re-anchor and inspect

confirm merge base;

verify no open overlap;

inspect current migration head;

inspect repository conformance patterns;

confirm B.2d fixture bytes.

Step 2 — Add ADR and contracts

review plan ref;

proposal/verdict models;

intent/receipt/submission;

record/state;

deterministic digest/ID helpers.

Step 3 — Add profile adapter

ready-plan validation;

plan ref/digest construction;

proposal translation;

deterministic fixture.

Step 4 — Add application service

capability enforcement;

scope checks;

confirmation binding;

head/revision preflight;

verdict closure;

contribution transformation;

state construction.

Step 5 — Add repository port

finalize/get/get_for_plan;

exact failure semantics.

Step 6 — Add in-memory adapter

shared state;

atomic preflight;

exact replay/conflict;

reload integrity.

Step 7 — Add migration/PostgreSQL adapter

transaction-local contribution helper;

new table;

atomic three-record write;

reconstruction.

Step 8 — Add adversarial proof

contract matrix;

profile adapter negatives;

authority matrix;

stale parent;

transaction failure injection;

persistence corruption;

no head/identity-decision changes.

Step 9 — Atomic docs sync

ADR;

architecture;

authority;

roadmap;

README;

contributing;

checked-in handoff.

§22 Verification commands

Core gates

uv sync --locked
uv run ruff check .
uv run pyright
uv run --no-dev python -c "import dungeonmind"
uv run --no-dev python -c "import dungeonmind_dnd"
uv run pytest -m "not integration"

Focused unit gates

uv run pytest -q \
  tests/unit/test_contribution_review_contract.py \
  tests/unit/test_contribution_review_service.py \
  tests/unit/test_contribution_review_memory_repository.py \
  tests/unit/test_dnd_threat_contribution_review_adapter.py \
  tests/unit/test_import_boundaries.py

Integration gate

DUNGEONMIND_DATABASE_URL=postgresql://dungeonmind:dungeonmind-dev@localhost:54329/dungeonmind \
  uv run pytest -q -m integration \
  tests/integration/test_postgres_contribution_review_repository.py

Migration gates

uv run alembic heads
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head

Exactly one head before and after.

No forbidden drift

git diff -- \
  src/dungeonmind/contracts/contribution.py \
  src/dungeonmind/contracts/identity.py \
  src/dungeonmind/contracts/graph.py \
  src/dungeonmind/service \
  src/dungeonmind/agents \
  src/dungeonmind_dnd/contracts \
  src/dungeonmind_dnd/profiles \
  src/dungeonmind_dnd/vocabularies \
  tests/fixtures/dungeonmind_dnd/tripod-null-calf-contribution-plan-v1.json \
  tests/fixtures/dungeonmind_dnd/tripod-null-calf-threat-candidates-v1.json \
  tests/fixtures/dungeonmind_dnd/gatewatch-world-graph-v3.json \
  uv.lock \
  compose.postgres.yml

Expected: empty.

No publication proof

rg -n \
  'PublishRevisionCommand|publish_revision|rollback_head|IdentityDecisionRepository|identity_decisions\.append' \
  src/dungeonmind/application/contribution_review.py \
  src/dungeonmind_dnd/application/contribution_review.py

Expected: no invocation. Importing WorldGraphRepository for read preflight is allowed; publication calls are not.

Import proof

uv run --no-dev python - <<'PY'
import sys
import dungeonmind
assert "dungeonmind_dnd" not in sys.modules
PY

uv run --no-dev python - <<'PY'
import sys
import dungeonmind_dnd.application.contribution_review

for forbidden in (
    "fastapi",
    "psycopg",
    "sqlalchemy",
    "openai",
    "anthropic",
):
    assert forbidden not in sys.modules
PY

Wheel proof

uv build
uv run python - <<'PY'
from pathlib import Path
from zipfile import ZipFile

wheel = sorted(Path("dist").glob("*.whl"))[-1]
with ZipFile(wheel) as archive:
    names = set(archive.namelist())

required = {
    "dungeonmind/contracts/contribution_review.py",
    "dungeonmind/application/contribution_review.py",
    "dungeonmind_dnd/application/contribution_review.py",
}
missing = sorted(required - names)
assert not missing, missing
PY
rm -rf dist

§23 Acceptance rubric

Boundary

Base is PR #9 merge commit or explicitly re-anchored descendant.

Kernel never imports dungeonmind_dnd.

D&D adapter imports no repositories/infrastructure/service/agents.

Existing contribution, identity, graph, and B.2d plan contracts unchanged.

No dependency/lockfile change.

No API/UI/tool/agent surface.

Review intent

Ready plan translates deterministically.

Blocked plan rejects.

Complete plan and preview digests preserved.

One proposal per candidate resolution.

One identity verdict per proposal.

One assertion verdict per assertion.

Intent digest binds all semantic content.

Authority

Commit effect evaluated through existing capability authority.

Exact confirm_commit category required.

GM admissibility required.

World/campaign/revision scope exact.

Confirmation receipt bound to exact intent.

Current head preflighted.

Exact parent revision/digest verified.

Review semantics

Candidate rejection closes all dependent assertions.

Create-new requires accepted label.

Relationship acceptance requires non-rejected candidate endpoints.

No target override.

All reviewed assertions accepted/rejected.

Node identity outcomes finalized correctly.

Relationship identity outcomes remain null.

Persistence

Candidate contribution stored superseded.

Reviewed successor stored active.

Review row stored finalized.

All three commit atomically.

Exact replay returns exact state.

Operation conflict fails closed.

Source plan finalizes once.

Reload verifies all fingerprints and cross-links.

Ordinary contribution repository can read both contributions.

PostgreSQL and memory semantics conform.

Negative authority

Graph head unchanged.

Revision count unchanged.

No publication command.

No identity-decision row.

No materialized graph payload.

Finalized review described as non-canonical.

Documentation

ADR-0007 accepted.

ADR-0006 points forward.

Architecture, authority, roadmap, README, contributing agree.

B.2d marked landed.

B.2e current.

B.2f remains explicitly false.

§24 Stop conditions

Stop and report if:

main contains overlapping review persistence or publication work.

A change to GraphContribution is required.

A change to IdentityDecisionRecord is required.

B.2d plan contracts or fixtures must change.

Profile package must import a repository or adapter.

Kernel must import dungeonmind_dnd.

Review cannot be persisted atomically with both contributions.

PostgreSQL contribution insertion cannot be reused inside one transaction without changing public behavior.

A mutable draft lifecycle is required for the proof.

Review replacement/cancellation is required.

A reviewer must choose a different identity target.

Relationship evidence must merge with an existing graph relationship.

Current-head preflight requires publication.

A graph schema change appears necessary.

A global identity-decision append appears necessary before materialization.

An API/UI/CLI/tool is required.

A new dependency is required.

More than one new migration is required.

Errors cannot remain prose-safe.

Documentation cannot truthfully state that graph truth remains unchanged.

Stop report:

Stop condition:
Discovered fact:
Affected invariant:
Paths/contracts involved:
Why B.2e cannot absorb it:
Smallest revised capability:
Safe work completed:
Work not attempted:
Operator decision required:

§25 What remains false after merge

Even after B.2e:

No review draft can be saved.

No review decision can be edited incrementally.

No finalized review can be cancelled, retracted, replaced, or superseded.

No review API exists.

No review UI exists.

No agent review tool exists.

No reviewer can redirect a candidate to another object.

No merge, split, unmerge, or alias operation is created.

No global IdentityDecisionRecord is appended.

No accepted assertion is materialized into a graph payload.

No graph revision is created.

No graph head advances.

No publication CAS occurs.

B.2e's head preflight does not guarantee B.2f's future CAS.

No zero-accepted-assertion publication behavior is defined.

No relationship evidence augmentation exists.

No assertion-scoped relationship model exists.

No LLM extraction runtime exists.

No source-opening capability exists.

No mechanics/statblock binding exists.

No Threat projection/hydration exists.

No product surface adopts the capability.

No second game system exists.

No generic profile interpretation layer exists.

dungeonmind_dnd remains in the same distribution.

§26 Named successors

B.2e.1 — Mutable review workspace and replacement

Only when a real review surface requires it:

open review
→ partial decision saves
→ optimistic concurrency
→ cancellation/retraction
→ explicit review supersession
→ audit history

This must not mutate B.2e finalized records in place.

B.2f — Accepted contribution materialization and publication

Outcome:

finalized B.2e review state
+ exact expected parent
→ deterministic dm_union_graph_v3 payload
→ global identity-decision records as needed
→ validation
→ atomic expected-parent CAS publication
→ revision-pinned receipt

B.2f must:

reload and verify B.2e state;

reject stale parent atomically;

create new objects only for accepted create_new candidates;

reuse confirmed existing IDs;

omit rejected assertions;

define zero-accepted-assertion behavior;

never silently replan or rereview.

B.3 — Threat mechanics-resource binding

Only after B.2f can publish a durable Threat identity:

published Threat identity
→ exact external mechanics resource reference
→ immutable revision/digest pin
→ profile-owned hydration

§27 Required PR handback

The PR body is the merge contract.

Exact state

Repository:
Branch:
Base SHA:
Head SHA:
PR number:
Migration revision/down_revision:
Changed paths:
Paths outside allowlist:
Forbidden contract changes:
Dependency/lockfile changes:

Capability matrix

Function

Input

Durable output

Mutates graph head?

build D&D review intent

ready B.2d plan + verdicts

none

no

finalize review

generic submission + policy + repos

review state + two contributions

no

load review

world/review ID

exact reconstructed state

no

Fixture identity

Record:

source plan ID/digest
review intent digest
operation ID
confirmation ID
review ID
candidate contribution ID/digests
reviewed contribution ID/digest
expected parent
assertion accepted/rejected counts
candidate verdicts

Authority proof

Record:

policy ID;

tool/effect/category;

world/campaign/revision scope;

GM admissibility;

confirmation receipt binding;

stale-head negative test.

Persistence proof

Record:

in-memory exact replay;

PostgreSQL exact replay;

operation conflict;

source-plan conflict;

atomic failure injection;

reload integrity corruption tests;

evidence persistence;

candidate/reviewed contribution lifecycle.

Negative write proof

Record before/after:

graph head
graph revision count
identity decision count

All unchanged.

Verification

Record actual:

Ruff;

Pyright;

focused tests;

full non-integration count;

integration count;

Alembic upgrade/downgrade;

import proof;

wheel proof;

CI;

no forbidden drift.

Remaining false

Copy §25 and remove only statements made true.

§28 Reviewer protocol

Review as a durable-governance write PR, not as a graph-publication PR.

Reconstruct intent

Before code review, state:

B.2e makes one complete review durable.

It persists a superseded candidate contribution, an active reviewed successor,
and a finalized review record under explicit GM commit authority.

It does not materialize or publish graph truth.

Adversarial review cases

Import kernel.

dungeonmind_dnd does not load.

Build intent from blocked plan.

rejected.

Remove one assertion verdict.

rejected.

Use create_new for resolved-existing candidate.

rejected.

Reject candidate but accept its relationship.

rejected.

Create new candidate but reject its label.

rejected.

Use player policy.

denied.

Use unpinned policy.

denied.

Reuse receipt for modified verdict.

rejected.

Advance head before finalization.

stale-parent error, no write.

Inject failure after candidate insert.

no rows survive.

Replay exact submission.

identical state.

Replay operation with changed verdict.

idempotency conflict.

Submit second operation for same plan.

already-finalized error.

Reload state after tampering with reviewed contribution.

persistence-integrity error.

Inspect candidate contribution.

superseded; assertions still candidate.

Inspect reviewed successor.

active; every assertion accepted/rejected.

Inspect graph repository.

head/revisions unchanged.

Inspect identity repository/table.

no new rows.

Search application code.

no publish_revision, no identity-decision append.

Approval bar

Approve only when the reviewer can truthfully say:

PR B.2e atomically and idempotently adopts one explicitly confirmed GM review of one exact ready plan into a reloadable durable review bundle. The candidate proposal remains preserved, the reviewed successor contains complete accepted/rejected and identity verdicts, and no graph truth, identity ledger, or head is changed.

§29 Opening directive for the implementation agent

Start from merge commit 1a4ee973725d51a188da1b1a7a67a987c85266fe. Implement exactly B.2e as a one-shot finalized review capability. Add generic DungeonMind review contracts, a D&D profile adapter that translates one valid ready DndThreatContributionPlan into a generic review intent, an explicit content-bound commit confirmation receipt, a kernel application service that enforces the existing confirm_commit capability policy with exact GM world/campaign/revision scope, and a new atomic review repository with in-memory and PostgreSQL implementations. A successful commit must persist one superseded candidate contribution, one active reviewed successor contribution, and one finalized review record; exact reload must reconstruct and verify all three. Every assertion and candidate proposal must receive a complete verdict. Do not change existing contribution, identity, graph, B.2d plan, vocabulary, or profile contracts. Do not add mutable drafts, review replacement, target overrides, API/UI/tooling

## §30 Review-cycle-1 amendment

The first review discovered four required corrections that remain within the
B.2e capability and do not change its architecture:

1. `ContributionReviewIntent` is profile-neutral. The kernel treats
   `source_plan_schema` as opaque provenance; the D&D adapter alone validates
   `dmdnd_threat_contribution_plan_v1`. The review adapter has a narrower import
   allowlist than B.2d planning modules, and a synthetic non-D&D intent proves
   the generic contract.
2. Reloaded durable state independently verifies all authority facts. The
   record/state validators preserve proposal/verdict target and planned-outcome
   compatibility, recompute the intent digest from the reconstructed active
   candidate preview and durable verdicts, and recompute the confirmation ID.
   Mutation tests cover target overrides, incompatible verdicts, assertion
   verdicts, plan references, reviewer/time, intent digests, and confirmation
   IDs.
3. Finalized review children are lifecycle-protected. Both memory and
   PostgreSQL `ContributionRepository.update_status` paths reject status
   mutation of candidate or reviewed IDs with
   `InvalidLifecycleTransitionError`; PostgreSQL checks the review table while
   holding the contribution row lock.
4. PostgreSQL proof is expanded to cover migration head/table expectations,
   transaction-trigger rollback after child writes and before review-row
   completion, operation/source-plan conflicts, reload corruption, lifecycle
   protection, and unchanged graph-head/revision/identity-decision counts.

### Amendment to the path allowlist

The following existing integration paths are added to the approved scope:

- `tests/integration/test_migrations.py` — update expected Alembic head and
  expected table set for `0002_contribution_reviews`;
- `tests/integration/conftest.py` — truncate `contribution_reviews` before
  `graph_contributions` so the PostgreSQL fixture respects foreign keys;
- `tests/integration/test_postgres_contribution_review_repository.py` —
  expand PostgreSQL atomicity, conflict, corruption, negative-write, and
  lifecycle proofs.

The existing memory and PostgreSQL repository paths already in the original
allowlist receive the lifecycle guard. No new migration, dependency, lockfile,
existing contribution/identity/graph contract, or product surface is added.

The original implementation changed `src/dungeonmind/application/__init__.py`
and `src/dungeonmind/domain/__init__.py` to preserve the repository's existing
package-level export convention: application ports/orchestration and domain
errors are exported from their layer packages. These two paths are explicitly
added to the amended scope; removing the exports would create an avoidable
package API regression.
