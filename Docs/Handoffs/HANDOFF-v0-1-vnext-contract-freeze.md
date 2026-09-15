# HANDOFF — V0.1: freeze the DungeonMind vNext contract surface

**Created:** 2026-09-14  
**Status:** ACTIVE — implementation dispatch after Steward PR #55 lands / rebase to its merge  
**Repository / branch:** `Drakosfire/DungeonMind` / implementation branch to be created from current `main` after PR #55  
**Dispatch handoff branch:** `handoff/v0-contract-freeze`  
**Predecessor:** PR #55 — `STEWARDSHIP: govern vNext roadmap execution`  
**Roadmap phase:** V0 — Contract freeze  
**Slice:** V0.1 — DungeonMind-owned contract definition  
**One-line mission:** Freeze one strict, domain-agnostic, versioned vNext data contract and one canonical machine-readable contract identity that DungeonMindBuddy can pin exactly in the V0.2 consumer/domain proof, without changing runtime behavior, persistence, graph authority, or current World APIs.

---

## §1 Outcome

At the end of this PR, DungeonMind publishes a **complete vNext contract family** as strict importable models under one intentional public namespace plus a checked-in canonical schema bundle whose aggregate digest is deterministic and reproducible.

The PR answers one question:

> **Can DungeonMind express the accepted vNext architecture as one exact, self-consistent, domain-agnostic wire/data contract without embedding DungeonBuddy/TTRPG semantics or changing any current behavior?**

The successful end state is:

```text
accepted vNext architecture
        ↓
strict versioned Python contract models
        ↓
deterministic checked-in schema bundle
        ↓
exact aggregate contract digest
        ↓
V0.2 DungeonMindBuddy can pin this artifact and prove its domain mapping
```

This PR does **not** claim overall `VNEXT_CONTRACT_FROZEN`.

Its success disposition is:

```text
V0_1_DUNGEONMIND_CONTRACT_FROZEN
```

Overall V0 remains incomplete until a separate DungeonMindBuddy PR consumes the exact contract identity and demonstrates that current campaign/GM-player/TTRPG semantics can be expressed without inventing fields locally.

---

## §2 Authority and required reading

Read in this order before writing code:

1. `Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md`
   - living Steward state;
   - current phase and merge discipline;
   - authority/read order;
   - cross-repository contract rule.

2. `Docs/Roadmaps/ROADMAP.md`
   - V0 primary question, required contract families, exit condition;
   - V1–V11 sequencing;
   - explicit prohibition on starting persistence/behavior in V0.

3. `Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`
   - semantic destination;
   - KnowledgeSpace / Entity / Assertion model;
   - generic scope, visibility, temporal, source/evidence, contribution, identity, projection contracts;
   - DomainContract vs SemanticProfile;
   - breaking inventory and bridge-genesis direction.

4. `Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md`
   - contract must permit candidate-local bounded reads;
   - bounded retrieval must not require a prebuilt full projection;
   - no serving/storage optimization belongs in this PR.

5. `Docs/Architecture/AUTHORITY.md`
   - source precedence;
   - exact revision authority;
   - evidence/source freshness;
   - governed writes;
   - chat/history is not authority.

6. `CONTRIBUTING.md`
   - contracts import boundary;
   - versioned durable contract discipline;
   - strict/no-extra fields;
   - type/lint/test gates.

7. Current contract seams on the exact implementation base:

   ```text
   src/dungeonmind/contracts/base.py
   src/dungeonmind/contracts/graph.py
   src/dungeonmind/contracts/contribution.py
   src/dungeonmind/contracts/knowledge_assertion.py
   src/dungeonmind/contracts/evidence.py
   src/dungeonmind/contracts/projection_v2.py
   src/dungeonmind/contracts/semantic_profile.py
   src/dungeonmind/contracts/identity.py
   src/dungeonmind/application/semantic_profiles.py
   ```

The current World-shaped contracts are evidence for semantics and naming lineage. They are not templates that must be mechanically preserved.

### Pre-dispatch re-anchor

PR #55 is open when this handoff is authored at head:

```text
4e062fe2acfd45005986e828c6b88ccdb6159bb6
```

Do not implement from a stale base merely to preserve this handoff SHA.

Before coding:

1. require PR #55 merged or explicitly rebase onto the current `main` that contains its Steward handoff;
2. record exact base SHA in the implementation PR;
3. re-read the current Steward checkpoint in case another accepted docs change altered V0.

---

## §3 Scope

### In scope

1. A new intentionally isolated public contract namespace, preferred shape:

   ```text
   src/dungeonmind/contracts/vnext/
   ```

   The exact internal file split is implementation latitude. The public import seam should be deliberate and readable, e.g.:

   ```python
   from dungeonmind.contracts.vnext import Assertion, KnowledgeRevision, ProjectionRequest
   ```

   Do not flood the legacy `dungeonmind.contracts` root export surface merely for convenience.

2. Strict versioned vNext data models for the full DungeonMind-owned V0 contract family described in §5.

3. Syntactic/shared validators necessary to make the contract self-consistent:
   - nonblank opaque IDs;
   - SHA-256 formatting;
   - qualified terms;
   - canonical-JSON-compatible values;
   - duplicate/contradictory nested entries;
   - discriminated-union shape invariants.

4. A deterministic schema-bundle generator.

5. One checked-in canonical schema bundle + manifest with:
   - bundle schema/version;
   - exact list of exported contract types;
   - canonical schema representation for each public model;
   - per-contract SHA-256;
   - one aggregate SHA-256 over the canonical manifest/bundle content.

6. Neutral contract fixtures proving the generic shape can express:
   - ordinary organization/project knowledge;
   - entity-valued relationships;
   - literal and term-valued assertions;
   - global and scoped knowledge;
   - generic visibility labels;
   - established/provisional/retracted standing;
   - asserted/inferred/speculative epistemic basis;
   - UTC and domain temporal forms;
   - evidence/source refs;
   - identity decisions;
   - typed contribution items;
   - projection request/snapshot identity.

7. Adversarial contract tests proving malformed/ambiguous wire shapes fail closed.

8. Package/import-boundary tests showing the new contract namespace remains stdlib + Pydantic only and introduces no DungeonBuddy, D&D, application, repository, infrastructure, database, API, or model-provider dependency.

### Out of scope — falsification

Any of the following means the PR has crossed its lease:

- repository protocols;
- in-memory/PostgreSQL adapters;
- migrations or Alembic changes;
- graph/read services;
- `KnowledgeReadContext`;
- parsed-revision/index implementation;
- publication/materialization behavior;
- legacy v1-v6 decoding changes;
- migration/bridge-genesis execution;
- current World API changes or deprecations;
- DungeonBuddy imports or product DTOs;
- a DungeonBuddy `DomainContract` implementation;
- D&D vocabulary changes;
- `dungeonmind_dnd` behavior changes;
- runtime domain-policy execution;
- plugin discovery/registration;
- performance claims;
- Buddy repin/cutover;
- live authority mutation;
- deletion of historical contracts.

This PR freezes **data shape**, not execution.

---

## §4 Binding contract principles

### 4.1 Strict by default

All public models inherit the existing strict contract behavior (`extra="forbid"`) directly or through a vNext strict base.

Unknown fields fail closed.

Do not add permissive `dict[str, Any]` escape hatches where the architecture defines a stable shape.

### 4.2 Version top-level durable/wire envelopes

Every durable/public envelope introduced by this slice carries an explicit literal `schema_version`.

Nested value objects do not need ceremonial schema fields if their owning top-level schema already pins their shape.

### 4.3 Opaque stable identity

IDs are nonblank opaque strings.

Do not infer entity type, tenant, authorization, campaign, or domain semantics from ID prefixes.

Existing prefixes such as `obj:` / `rev:` remain legal values where migration later preserves IDs, but the contract does not require semantic prefixes.

### 4.4 Qualified terms are syntax, not ontology

Use the already-proven qualified-term syntax:

```text
namespace:local
```

lowercase letters/digits with `.`, `_`, `-`, exactly one colon.

Examples:

```text
organization.scope:team
dungeonbuddy.visibility:gm
dnd5e:member_of
```

The contract validates syntax only.

A semantic profile/domain contract later decides which terms are admitted.

### 4.5 JSON means canonical JSON-compatible values

Literal/domain metadata values must reject:

```text
NaN / Infinity
non-string object keys
sets / tuples / arbitrary Python objects
```

No JSON-inside-a-string transport.

### 4.6 Genericity does not remove governance axes

Every assertion shape must retain explicit places for:

```text
scope
visibility
epistemic_basis
claim_mode
standing
evidence_ref_ids
temporal_scope
domain_metadata
```

Do not simplify these away in the name of a generic property graph.

### 4.7 Domain semantics are qualified data

The Kernel contract must not define enums for:

```text
GM
PLAYER
campaign
session
NPC
canon
fictional time
rulebook/prep/worldbuilding as required source families
```

DungeonBuddy may use those meanings later through qualified terms and domain descriptors.

### 4.8 DomainContract is not executable plugin code

The durable contract may name a pure admission-policy identity.

It must not carry:

```text
Python module paths
callables
import strings
URLs for executable code
arbitrary hooks
```

Runtime resolution belongs to a later application-layer slice.

### 4.9 Contract must permit candidate-local reads

`ProjectionRequest` describes authority/admission context.

It must **not** contain or require a fully materialized projection result.

Nothing in the V0 contract should force future operations into:

```text
full projection → bounded lookup
```

### 4.10 No semantic reinterpretation of existing schemas

Current schemas remain immutable historical contracts.

Create new vNext contract families/versions. Do not silently edit `dm_graph_revision_v1`, `dm_source_artifact_v2`, `dm_identity_decision_v2`, etc.

---

## §5 Required vNext contract surface

Names below are the design target. Small Python class-name adjustments are acceptable only if schema names and semantics stay explicit and the PR handback records them. Do not invent a second competing vocabulary.

### 5.1 Common generic values

Required concepts:

```text
QualifiedTerm
JsonValue
KnowledgeStanding = established | provisional | retracted
EpistemicBasis = asserted | inferred | speculative
DomainMetadataEntry
```

`DomainMetadataEntry` should be structurally typed:

```text
schema: QualifiedTerm
payload: JsonValue
```

rather than an untyped free-form property bag.

### 5.2 Scope

```text
ScopeBinding
  axis: QualifiedTerm
  value: nonblank string

ScopeSelector
  include_unscoped: bool
  bindings: list[ScopeBinding]
  wildcard_axes: list[QualifiedTerm]
```

Contract invariants:

- no duplicate `(axis, value)` bindings;
- no duplicate wildcard axes;
- an axis may not be both explicitly bound and wildcarded in one selector.

No binding means space-global knowledge.

### 5.3 Visibility

Discriminated union:

```text
PublicVisibility
  kind = public

LabelsAnyVisibility
  kind = labels_any
  labels: non-empty unique QualifiedTerm[]

LabelsAllVisibility
  kind = labels_all
  labels: non-empty unique QualifiedTerm[]
```

Public alias/type:

```text
VisibilityRequirement
```

No GM/PLAYER enum exists here.

### 5.4 Temporal scope

Discriminated union:

```text
UnknownTemporalScope
  kind = unknown

TimelessTemporalScope
  kind = timeless

UtcIntervalTemporalScope
  kind = utc_interval
  valid_from?
  valid_until?

DomainTemporalScope
  kind = domain_ref
  schema: QualifiedTerm
  payload: JsonValue
```

`utc_interval` must contain at least one bound and reject `valid_until < valid_from` when both are present.

Unknown and timeless remain distinct.

### 5.5 Domain contract

Top-level durable/wire models:

```text
DomainContractRef
  schema_version = dm_domain_contract_ref_v1
  domain_id
  domain_revision
  descriptor_sha256

DomainContractDescriptor
  schema_version = dm_domain_contract_v1
  domain_id
  domain_revision
  scope_axes[]
  visibility_labels[]
  claim_modes[]
  temporal_extension_schemas[]
  domain_metadata_schemas[]
  source_annotation_schemas[]
  admission_policy_id
```

Lists are deterministic/unique.

`admission_policy_id` is opaque identity only.

Do not embed implementation location.

### 5.6 Semantic profile v2

Reuse the accepted `SemanticProfileRef` identity concept rather than minting a new ref solely for vNext.

Add a new descriptor generation:

```text
SemanticProfileDescriptorV2
  schema_version = dm_semantic_profile_v2
  profile_id
  profile_revision
  term_namespaces[]
  predicates[]
  classification_terms[]
```

Predicate spec:

```text
term: QualifiedTerm
allowed_value_kinds: unique subset of
  entity_ref | literal | term_ref
literal_schema?: JsonValue
```

The descriptor is data-only.

No ontology reasoner or runtime validation engine in this PR.

### 5.7 Entity and assertion graph

```text
Entity
  schema_version = dm_entity_v1
  entity_id
```

Assertion values are a discriminated union:

```text
EntityRefValue
  kind = entity_ref
  entity_id

LiteralValue
  kind = literal
  value: JsonValue

TermRefValue
  kind = term_ref
  term: QualifiedTerm
```

Assertion metadata:

```text
AssertionMetadata
  scope: ScopeBinding[]
  visibility: VisibilityRequirement
  epistemic_basis: EpistemicBasis
  claim_mode: QualifiedTerm
  standing: KnowledgeStanding
  evidence_ref_ids: unique string[]
  temporal_scope: TemporalScope
  domain_metadata: DomainMetadataEntry[]
```

Assertion:

```text
Assertion
  schema_version = dm_assertion_v1
  assertion_id
  subject_entity_id
  predicate: QualifiedTerm
  value: AssertionValue
  metadata: AssertionMetadata
```

A relationship is therefore an assertion with `EntityRefValue`; there is no separate vNext relationship authority record.

### 5.8 Identity

Alias record:

```text
IdentityAlias
  schema_version = dm_identity_alias_v1
  alias_id
  entity_id
  alias_text
  evidence_ref_ids[]
  standing
```

New identity decisions continue the existing identity schema lineage and retain the currently earned generic decision vocabulary.

Preferred shape:

```text
IdentityDecisionV3
  schema_version = dm_identity_decision_v3
  decision_id
  space_id
  decision_kind
  subject_entity_ids[]
  target_entity_ids[]
  alias?
  actor
  reason?
  reversible
  supersedes_decision_ids[]
  status
  created_at
```

The existing generic kinds remain available unless implementation discovers a direct contradiction with the accepted architecture:

```text
alias_add
alias_remove
merge
split
unmerge
reject_candidate
mark_ambiguous
human_override
```

Preserve the existing kind cardinality invariants, translated from object IDs to entity IDs.

Do not carry World-specific merge side-effect payloads merely because v2 had them. Those belong to later behavior/migration design unless V0.1 can prove they are part of the public semantic contract.

If omitting them prevents historical/new decision reconstructibility, STOP and rebrief rather than sneaking them into the new schema.

### 5.9 Sources and evidence

New generic source generations:

```text
SourceArtifactV3
  schema_version = dm_source_artifact_v3
  source_artifact_id
  source_classification: QualifiedTerm
  current_revision_id?
  authority: primary | derived | reference
  visibility: VisibilityRequirement
  status: active | superseded | retracted
  uri?
  foreign_refs[]
  domain_metadata[]
  created_at?
  updated_at?

SourceRevisionV2
  schema_version = dm_source_revision_v2
  source_revision_id
  source_artifact_id
  content_sha256
  body_storage
  locator?
  created_at

EvidenceRefV3
  schema_version = dm_evidence_ref_v3
  evidence_ref_id
  source_artifact_id
  source_revision_id?
  evidence_role: support | contradiction | context
  can_open_source
  can_highlight_span
  locator?
  uri?
  source_locator?
  line_ref?
  source_span_ref_id?
  domain_metadata[]
```

No mandatory:

```text
world_id
campaign_id
session_id
SourceDomain
GM/PLAYER Visibility
```

A rulebook/session recap/etc. can later be expressed by `source_classification` and domain metadata.

### 5.10 Knowledge revisions and head

```text
MigrationOriginRef
  source_system
  source_root_id
  source_revision_id
  source_payload_sha256
  migration_manifest_sha256

KnowledgeRevision
  schema_version = dm_knowledge_revision_v1
  space_id
  revision_id
  parent_revision_id?
  created_at
  operation_ids: non-empty unique[]
  graph_schema
  graph_payload_sha256
  domain_contract_ref
  semantic_profile_ref
  migration_origin_ref?
  status = published

KnowledgeHead
  schema_version = dm_knowledge_head_v1
  space_id
  head_revision_id
  updated_at
```

Publication command:

```text
PublishKnowledgeRevisionCommand
  schema_version = dm_publish_knowledge_revision_command_v1
  space_id
  parent_revision_id?
  expected_parent_revision_id?
  operation_ids[]
  graph_schema
  graph_payload: JsonValue/object
  domain_contract_ref
  semantic_profile_ref
  migration_origin_ref?
  created_at
```

Contract invariant survives exactly:

```text
parent_revision_id == expected_parent_revision_id
```

Repository comparison to the actual current head remains later behavior.

### 5.11 Contribution contract

Top-level:

```text
KnowledgeContribution
  schema_version = dm_knowledge_contribution_v1
  contribution_id
  space_id
  producer
  produced_at
  source_refs[]
  status
  supersedes_contribution_id?
  items[]
  diagnostics
```

`producer` is provenance identity, not authority.

Use a discriminated contribution-item union:

```text
ProposeEntity
  kind = propose_entity
  entity

ProposeAssertion
  kind = propose_assertion
  assertion

RetractAssertion
  kind = retract_assertion
  target_assertion_id

SupersedeAssertion
  kind = supersede_assertion
  target_assertion_id
  replacement_assertion

ProposeIdentityDecision
  kind = propose_identity_decision
  decision
```

Do not recreate the current nullable assertion bag.

Define an explicit disposition record for later governance output:

```text
ContributionDisposition
  schema_version = dm_contribution_disposition_v1
  item_index / stable item ref
  disposition = accepted | rejected | unresolved
  identity_decision_ids[]
  reason_code?
  domain_metadata[]
```

Exact stable-item-reference shape may be chosen in implementation, but it must be deterministic and must not depend on list position **unless list position is explicitly frozen as contract identity**. Prefer explicit `item_id` if that keeps replay/mutation semantics clearer.

### 5.12 Projection contract

```text
FocusRef
  kind: QualifiedTerm
  id: nonblank string

ProjectionRequest
  schema_version = dm_knowledge_projection_request_v1
  space_id
  revision_id?        # null = resolve current head later
  scope_selector
  audience_labels[]
  standing_selector[]
  focus[]
  domain_context[]

ProjectionSnapshot
  schema_version = dm_knowledge_projection_snapshot_v1
  space_id
  revision_id
  head_revision_id
  is_head
  domain_contract_ref
  semantic_profile_ref
  scope_selector
  audience_labels[]
  standing_selector[]
  focus[]
  projected_at
```

This contract describes the exact authority lens.

It does not define a full graph result as a prerequisite to point reads.

Audience labels and selectors must be deterministic/unique.

---

## §6 Canonical schema bundle and contract identity

The cross-repository handoff must be based on an exact artifact, not “equivalent-looking code.”

### Required checked-in artifact

Preferred location:

```text
Docs/Contracts/vnext/dm_vnext_contract_v1.json
```

or another single obvious repository path agreed during implementation.

The artifact contains:

```text
bundle_schema = dm_vnext_contract_bundle_v1
contract_family = dungeonmind-vnext
contract_revision = v1
contracts[]
aggregate_sha256
```

Each contract entry contains at least:

```text
public_name
schema_version / nested-type identity
canonical_json_schema
schema_sha256
```

The aggregate digest is computed over canonical bundle content **excluding the aggregate field itself** or over an explicitly named manifest payload. Pick one algorithm, document it, and pin a test vector.

Do not define a recursive self-hash accidentally.

### Generator

Add a small deterministic generator/check command, preferred under:

```text
scripts/generate_vnext_contract_bundle.py
```

Required modes may be simple:

```text
--output <path>
--check <checked-in-path>
```

`--check` must fail if generated canonical bytes differ from the checked-in artifact.

No network access.

No timestamps, machine paths, Python object reprs, nondeterministic `$defs` ordering, or environment-specific metadata in the artifact.

### Why checked-in JSON Schema

The checked-in schema bundle is the V0 cross-repository wire artifact.

DungeonMindBuddy V0.2 should pin/copy/verify its exact aggregate digest rather than regenerate a supposedly equivalent schema independently.

Equivalent semantics with a different unreviewed artifact is drift until explicitly accepted.

---

## §7 Fixture requirements

V0.1 fixtures prove contract expressiveness only. They do not prove application admission behavior.

### Fixture A — generic organizational memory

Use synthetic, non-TTRPG names.

Represent at minimum:

```text
Priya
Marco
Retrieval Evaluation
Research Team
```

Assertions should demonstrate:

```text
organization:owns        entity_ref
organization:member_of   entity_ref
organization:title       literal
organization:classification term_ref
```

Include:

- one unscoped assertion;
- one project/team scope binding;
- public and label-gated visibility;
- one UTC validity interval;
- source/evidence identity.

### Fixture B — temporal supersession shape

Represent:

```text
Priya owns Retrieval Evaluation until 2026-09-07
Marco owns Retrieval Evaluation from 2026-09-07
```

Do not implement temporal inference.

Only prove both assertions can be represented distinctly and round-trip exactly.

### Fixture C — adversarial epistemic/identity shape

Represent, as data only:

```text
conflicting assertions
belief-like and fact-like claim_mode terms
speculative epistemic basis
provisional + retracted standing
restricted visibility labels
ambiguous/rejected identity decision data
merge/split/unmerge compatible identity shapes
multiple evidence supports
```

The fixture demonstrates that genericity did not erase governance dimensions.

### Deliberately absent from V0.1 fixtures

Do not make DungeonMind own a canonical DungeonBuddy campaign fixture in this PR.

The required DungeonBuddy preservation fixture belongs to V0.2 in the consumer repository and must pin the exact V0.1 contract digest.

---

## §8 Expected write lease

Preferred production paths:

```text
src/dungeonmind/contracts/vnext/__init__.py
src/dungeonmind/contracts/vnext/common.py
src/dungeonmind/contracts/vnext/domain.py
src/dungeonmind/contracts/vnext/knowledge.py
src/dungeonmind/contracts/vnext/source.py
src/dungeonmind/contracts/vnext/contribution.py
src/dungeonmind/contracts/vnext/projection.py
```

File split may be adjusted for readability.

Supporting paths:

```text
scripts/generate_vnext_contract_bundle.py
Docs/Contracts/vnext/dm_vnext_contract_v1.json
tests/fixtures/vnext/... neutral fixtures
tests/unit/test_vnext_contracts.py
tests/unit/test_vnext_contract_bundle.py
tests/unit/test_import_boundaries.py   # only if new package path needs explicit boundary proof
Docs/Handoffs/HANDOFF-v0-1-vnext-contract-freeze.md
```

Potential public package export:

```text
src/dungeonmind/contracts/vnext/__init__.py
```

Avoid modifying the legacy root `src/dungeonmind/contracts/__init__.py` unless a concrete package/public-import reason requires it.

### Bounded discovery

Up to two additional **contract/test/script/docs** paths are allowed if required to share canonical JSON validation/hash helpers cleanly.

Any application, infrastructure, migration, API, `dungeonmind_dnd`, or PostgreSQL path is a STOP/rebrief condition.

No dependency or lockfile changes are expected.

---

## §9 Work plan

1. **Re-anchor and freeze names.**
   - Re-read current architecture + Steward handoff.
   - Confirm PR #55 merged and record exact base.
   - Create implementation branch from that base.
   - Before large code volume, write a compact contract inventory in the PR/handoff showing final class/schema names.

2. **Build shared strict values.**
   - qualified terms;
   - finite JSON values;
   - SHA-256 strings;
   - nonblank opaque IDs;
   - generic standing/epistemic/domain metadata.

3. **Land domain/scope/visibility/temporal contracts.**
   - no domain-specific enums;
   - discriminated unions deterministic;
   - duplicate/ambiguous selectors rejected.

4. **Land entity/assertion/identity contracts.**
   - relationship represented only through `EntityRefValue`;
   - metadata axes mandatory;
   - current generic identity-decision semantics preserved where still applicable.

5. **Land generic source/evidence contracts.**
   - no world/campaign/session/GM assumptions;
   - source classification is qualified domain data;
   - evidence role remains generic.

6. **Land revision/head/publication command contracts.**
   - exact parent/CAS token equality contract;
   - domain/profile refs pinned;
   - migration origin representable but not executed.

7. **Land typed contribution contracts.**
   - discriminated items;
   - no nullable assertion bag;
   - no human Graph Review workflow encoded as Kernel requirement.

8. **Land projection request/snapshot contracts.**
   - generic scope + audience + standing;
   - no precomputed projection requirement.

9. **Generate and pin schema bundle.**
   - deterministic generator;
   - per-contract and aggregate digests;
   - checked-in canonical bytes.

10. **Add neutral/adversarial fixtures and negative tests.**
    - strict round-trip;
    - unknown fields rejected;
    - malformed unions rejected;
    - duplicate selectors/labels/evidence IDs rejected;
    - noncanonical JSON values rejected;
    - no TTRPG terms appear in Kernel enums/field names.

11. **Run broad regression gates.**
    - current World runtime behavior must remain unchanged;
    - no migration/adapter changes;
    - import boundaries remain clean.

12. **Hand back exact contract identity.**
    - aggregate digest;
    - changed paths;
    - schema inventory;
    - exact reviewed head;
    - what remains false;
    - explicit V0.2 dispatch pointer.

---

## §10 Acceptance gates

### Focused contract tests

Must prove at minimum:

1. every public top-level vNext model rejects unknown fields;
2. every top-level schema version is exact and immutable;
3. qualified terms accept valid current syntax and reject uppercase/multiple-colon/blank/malformed terms;
4. literal/domain metadata rejects non-finite/non-JSON values;
5. `AssertionValue` discriminates entity/literal/term values with no ambiguous shape;
6. assertion metadata requires all governance axes;
7. scope selector duplicate/overlap invariants hold;
8. visibility any/all require non-empty unique labels;
9. unknown and timeless temporal forms remain distinct;
10. UTC interval ordering is validated;
11. DomainContract descriptor cannot contain executable module/path/callback fields because none exist;
12. SemanticProfileDescriptorV2 predicates use only admitted qualified-term syntax and known value-kind enum values;
13. SourceArtifactV3 contains no World/campaign/session fields;
14. EvidenceRefV3 contains no required TTRPG source-domain enum;
15. `IdentityDecisionV3` preserves merge/split/unmerge cardinality validation with entity IDs;
16. `KnowledgeRevision` pins DomainContract + SemanticProfile refs;
17. publish command enforces parent == expected parent;
18. typed contribution items reject nullable-bag style mixed shapes;
19. projection request can be instantiated without any full projection payload;
20. all three neutral fixtures round-trip deterministically.

### Bundle proof

Run generator twice to independent temp outputs and prove byte equality.

Then prove checked-in artifact equality:

```bash
uv run python scripts/generate_vnext_contract_bundle.py --output /tmp/vnext-a.json
uv run python scripts/generate_vnext_contract_bundle.py --output /tmp/vnext-b.json
cmp /tmp/vnext-a.json /tmp/vnext-b.json
uv run python scripts/generate_vnext_contract_bundle.py --check Docs/Contracts/vnext/dm_vnext_contract_v1.json
```

Exact command names may differ if implementation chooses a cleaner CLI. The proof may not.

### Required repository gates

```bash
uv sync --locked
uv run pytest -q tests/unit/test_vnext_contracts.py tests/unit/test_vnext_contract_bundle.py tests/unit/test_import_boundaries.py
uv run ruff check .
uv run pyright
uv run pytest -m "not integration"
uv run --no-dev python -c "import dungeonmind; import dungeonmind.contracts.vnext"
git diff --check
```

No PostgreSQL integration behavior is introduced, but run the repository-required CI/integration collection/gate before merge according to current `CONTRIBUTING.md` and report any inherited skips/failures honestly.

### Diff guards

The handback must explicitly prove no changes under:

```text
src/dungeonmind/application/
src/dungeonmind/infrastructure/
src/dungeonmind_dnd/
migrations/ or alembic/
```

and no dependency/lockfile changes unless a stop/rebrief was approved.

---

## §11 Stop conditions

Stop and return to Steward/design instead of improvising if any of these occur:

1. Buddy/TTRPG semantics appear necessary in the generic contract as fixed enums/fields.
2. A contract cannot express the accepted architecture without adding a new major concept not present in the vNext docs.
3. The implementation needs application/repository behavior to validate the wire shape.
4. A migration is needed just to define the contract.
5. The contract needs executable plugin hooks or module-path callbacks.
6. A historical current schema would have to be edited in place.
7. `SemanticProfileRef` cannot be reused without weakening historical semantics; do not silently fork it.
8. Identity v2 merge side effects appear semantically required in new vNext identity records; report exactly why before carrying historical storage machinery forward.
9. SourceRevision cannot remain a simple immutable body identity without a newly discovered generic semantic need.
10. Contract generation is nondeterministic because of tooling/version behavior that cannot be normalized safely.
11. Pydantic-generated schema cannot serve as a stable checked-in cross-repo artifact without a second normalized representation; design that normalization explicitly rather than ignoring drift.
12. Any performance/runtime implementation starts appearing because the contract “makes it easy.” That belongs to V1+.

Required stop report:

```text
Stop condition:
Exact contract/model affected:
Accepted architecture expectation:
Observed contradiction:
Why a local workaround would create drift:
Options considered:
Recommended architecture/roadmap change:
V0.1 state:
V0.2 impact:
```

---

## §12 What remains false after V0.1

Even after successful merge:

- overall V0 is not complete;
- DungeonMindBuddy has not pinned the contract bundle;
- no DungeonBuddy DomainContract exists;
- no campaign/GM-player preservation proof exists under vNext;
- no `KnowledgeSpace` repository exists;
- no vNext revision is durable;
- no `ParsedKnowledgeRevision` exists;
- no vNext derived indexes exist;
- no `KnowledgeReadContext` exists;
- no lazy point-read behavior exists;
- no generic admission engine exists;
- no vNext governed publication implementation exists;
- no bridge-genesis migration exists;
- no World history has been migrated or rewritten;
- no Buddy pin/cutover has happened;
- no old current/public path has been deleted;
- no performance improvement is claimed by this PR.

The contract is a promise, not yet an implementation.

---

## §13 Handback requirements

Return all of the following:

### Repository identity

```text
repo
branch
base SHA
head SHA
PR number / URL / state
commit list
changed-file list
paths outside lease, if any
```

### Contract inventory

For every public vNext top-level model:

```text
Python public name
schema_version
owning module
schema SHA-256 in bundle
```

Also return:

```text
contract bundle path
bundle aggregate SHA-256
generator command
check command
```

### Design decisions

For any place where the architecture document allowed implementation latitude, record:

```text
question
evidence
decision
rejected alternatives
consequence
reversal path
```

At minimum explicitly discuss:

- `SemanticProfileRef` reuse;
- identity-decision v3 shape / merge-side-effect disposition;
- contribution item stable identity;
- canonical schema-bundle hash algorithm;
- source revision versioning choice.

### Verification

Exact commands + results for:

```text
focused vNext tests
bundle determinism/check
ruff
pyright
full non-integration suite
required integration/CI gate
core/lightweight import
diff check
forbidden-path diff guard
```

### Fixture proof

Return fixture paths + canonical SHA-256 values and a short statement of what each demonstrates.

### What remains false

Copy/update §12 explicitly. Never imply V0 completion.

### Disposition

Only one of:

```text
V0_1_DUNGEONMIND_CONTRACT_FROZEN
V0_1_HOLD
V0_1_REBRIEF_REQUIRED
```

### Named successor

If frozen, dispatch:

> **V0.2 — DungeonMindBuddy contract pin + DomainContract preservation proof**

V0.2 must consume the exact V0.1 aggregate contract digest and prove that current DungeonBuddy world/campaign/cross-campaign, GM/player, fictional-time, source-classification, and World-object semantics can be represented through the generic contract without local field invention.

Only after that consumer proof may the Steward mark:

```text
VNEXT_CONTRACT_FROZEN
```

and advance DungeonMind implementation work to V1.

---

## §14 Review lens for the Steward

This PR should feel slightly boring.

That is a feature.

The Steward should reject clever runtime architecture hiding inside contract code.

The review questions are:

1. **Is every accepted vNext concept expressible?**
2. **Did any World/TTRPG semantic leak back into the Kernel?**
3. **Is the shape strict enough that Buddy cannot silently reinterpret it?**
4. **Is the machine-readable contract identity deterministic enough to pin across repositories?**
5. **Did the PR leave all current runtime/storage behavior untouched?**
6. **Can V0.2 discover a missing contract honestly instead of working around it?**

The merge-worthy outcome is not “lots of models exist.”

It is:

> **DungeonMind has published one exact language for vNext knowledge, and the next repository can now attempt to speak it without guessing.**
