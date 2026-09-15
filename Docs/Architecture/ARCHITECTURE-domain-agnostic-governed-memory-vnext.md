# DungeonMind vNext — Domain-Agnostic Governed Memory Graph

**Design status:** proposed breaking contract  
**Design anchor:** DungeonMind `main` at `d8f7a9f0d6b256f5cf4588987520bf286f1eade3`  
**Implementation posture:** contract first; no compatibility-driven distortion  
**Primary decision:** DungeonMind becomes a domain-agnostic governed knowledge graph. DungeonBuddy becomes a domain provider and consumer.

## Executive decision

The next Kernel should be built around this hierarchy:

```text
KnowledgeSpace
  └─ immutable KnowledgeRevision lineage
       └─ KnowledgeGraphSnapshot
            ├─ Entity
            ├─ Assertion
            └─ EvidenceRef

Governance
  ├─ KnowledgeContribution
  ├─ ContributionDisposition
  └─ IdentityDecision

Interpretation
  ├─ DomainContract
  └─ SemanticProfile

Projection
  ├─ exact revision
  ├─ generic scope selector
  ├─ generic visibility/audience labels
  ├─ generic standing/provenance checks
  └─ domain admission policy
```

The durable ownership boundary currently represented by `world_id` becomes **`KnowledgeSpace` / `space_id`**.

A KnowledgeSpace means exactly:

> one durable authority namespace with one immutable revision lineage and one explicit CAS-controlled head.

It does not mean world, campaign, project, user, team, game, organization, or assistant.

DungeonBuddy may define:

```text
space_id = eldyrwild
```

and treat that space as a fictional world.

Another consumer may define:

```text
space_id = organization-memory
```

without the Kernel learning what an organization is.

The existing `world_id` **values should be preserved during migration**. Eldyrwild does not receive a new root identity merely because the field changes from `world_id` to `space_id`.

---

## 1. vNext conceptual model

### 1.1 KnowledgeSpace

```text
KnowledgeSpace
  space_id
```

A space owns:

- one explicit mutable head;
- zero or more immutable revisions;
- governed contributions;
- identity decisions;
- domain/profile identity used to interpret its revisions.

There is no second graph per scope.

Campaign, project, team, session, meeting, etc. are contextual scope inside one space.

### 1.2 KnowledgeRevision

```text
KnowledgeRevision
  schema_version
  space_id
  revision_id
  parent_revision_id
  created_at
  operation_ids
  graph_schema
  graph_payload_sha256
  domain_contract_ref
  semantic_profile_ref
  migration_origin_ref?
  status = published
```

The existing invariants survive unchanged in substance:

```text
immutable revision
explicit head
expected-parent CAS
rollback by head movement
content digest
exact historical identity
```

`domain_contract_ref` and `semantic_profile_ref` are pinned revision inputs. A historical graph must not silently acquire the semantics of a later domain contract.

### 1.3 Entity

An entity is deliberately small.

```text
Entity
  entity_id
```

An Entity is a durable identity anchor.

The Kernel does not require:

```text
npc
person
location
faction
project
organization
document
rule
```

as entity kinds.

Those classifications are knowledge about an entity and belong to the domain vocabulary.

For example:

```text
entity = lysandra

lysandra
  dungeonbuddy:classification
  → dungeonbuddy:person

lysandra
  dungeonbuddy:role
  → dungeonbuddy:npc
```

`NPC` therefore does not survive as a Kernel concept.

The Kernel may continue to own identity-resolution machinery—aliases, merge, split, unmerge, ambiguity—but not the domain interpretation of the entity.

### 1.4 Assertion

The generic factual unit becomes:

```text
Assertion
  assertion_id
  subject_entity_id
  predicate
  value
  metadata
```

`predicate` is a qualified domain term.

`value` is a discriminated union:

```text
EntityRefValue
  entity_id

LiteralValue
  value: canonical JSON value

TermRefValue
  term: qualified term
```

This removes the current distinction between “attribute” and “relationship” from Kernel storage semantics.

A relationship is:

```text
subject = lysandra
predicate = dungeonbuddy:member_of
value = EntityRef(mirathorn_guard)
```

An attribute is:

```text
subject = lysandra
predicate = dungeonbuddy:occupation
value = Literal("guard captain")
```

A classification is:

```text
subject = lysandra
predicate = dungeonbuddy:classification
value = TermRef(dungeonbuddy:person)
```

Graph traversal can efficiently index entity-valued assertions without making “relationship” a separate authority model.

### 1.5 Identity aliases

Aliases remain Kernel identity machinery because entity reconciliation must not depend on a product ontology.

They should not become arbitrary domain properties.

Conceptually:

```text
IdentityAlias
  alias_id
  entity_id
  alias_text
  evidence_ref_ids
  status
```

Alias addition/removal remains governed and reversible.

Domain-specific names, titles, ranks, nicknames, etc. may still be ordinary assertions when their semantics are not identity equivalence.

### 1.6 Assertion metadata

The new metadata separates universal governance from domain meaning:

```text
AssertionMetadata
  scope
  visibility
  epistemic_basis
  claim_mode
  standing
  evidence_ref_ids
  temporal_scope
  domain_metadata[]
```

The important decision is that these are no longer one TTRPG enum bundle.

#### Universal `epistemic_basis`

Kernel-owned:

```text
asserted
inferred
speculative
```

This describes **how the assertion was derived**.

It is deliberately not:

```text
fact
belief
plan
event
rumor
```

Those describe what kind of claim something is.

#### Domain-owned `claim_mode`

Required qualified term:

```text
dungeonbuddy:fact
dungeonbuddy:belief
dungeonbuddy:rumor
dungeonbuddy:plan

organization:fact
organization:observed_event
organization:plan
organization:belief
```

This fixes an existing conceptual conflation.

`fact` should no longer sit beside `asserted` in the same Kernel enum.

Likewise `source_derived_candidate` belongs to contribution/governance state, not the epistemic character of an already materialized assertion.

#### Universal standing

Kernel-owned:

```text
established
provisional
retracted
```

This replaces `CanonState` as the generic authority concept.

DungeonBuddy may present:

```text
established → canonical
```

but “canon” is no longer Kernel vocabulary.

Rejected and unresolved knowledge remains contribution state and does not become an established graph assertion.

---

## 2. Generic scope contract

Campaign scope becomes one specialization of a generic scope constraint.

### 2.1 Scope binding

```text
ScopeBinding
  axis: QualifiedTerm
  value: str
```

Examples:

```text
axis = dungeonbuddy.scope:campaign
value = C2
```

```text
axis = organization.scope:team
value = research
```

```text
axis = assistant.scope:project
value = DungeonMind
```

An assertion carries zero or more scope bindings.

No bindings means:

> space-global knowledge.

### 2.2 Projection selector

```text
ScopeSelector
  include_unscoped: bool
  bindings: list[ScopeBinding]
  wildcard_axes: list[QualifiedTerm]
```

Generic Kernel admission is deterministic.

For every scope binding on an assertion, at least one must be true:

```text
projection contains exact axis/value
OR
projection wildcards that axis
```

All assertion scope axes must be satisfied.

Unscoped assertions are admitted only when `include_unscoped=true`.

#### DungeonBuddy mapping

Current `WORLD`:

```text
include_unscoped = true
bindings = []
wildcard_axes = []
```

Current `CAMPAIGN / C2`:

```text
include_unscoped = true
bindings = [
  dungeonbuddy.scope:campaign = C2
]
wildcard_axes = []
```

Current `WORLD_CROSS_CAMPAIGN`:

```text
include_unscoped = true
bindings = []
wildcard_axes = [
  dungeonbuddy.scope:campaign
]
```

This is the key reason `ScopeModeV2` should disappear from the generic Kernel.

### 2.3 Focus

Focus remains separate from scope.

```text
FocusRef
  kind: QualifiedTerm
  id: str
```

Examples:

```text
dungeonbuddy.focus:session / 28
organization.focus:meeting / 2026-09-14
assistant.focus:task / kernel-design
```

Kernel rule:

> If a contextual value controls whether knowledge is authorized/admitted, it must be represented as scope or visibility—not hidden inside `focus`.

Focus may influence domain retrieval, ranking, presentation, or context assembly. It is not silently an authorization dimension.

---

## 3. Generic visibility and admissibility

`GM` and `PLAYER` leave Kernel vocabulary.

### 3.1 VisibilityRequirement

```text
VisibilityRequirement =
    Public
  | LabelsAny(labels[])
  | LabelsAll(labels[])
```

Labels are qualified terms declared by the domain contract.

DungeonBuddy can define:

```text
dungeonbuddy.visibility:player
dungeonbuddy.visibility:gm
```

A PLAYER projection receives effective audience labels:

```text
{ dungeonbuddy.visibility:player }
```

A GM projection receives:

```text
{
  dungeonbuddy.visibility:player,
  dungeonbuddy.visibility:gm
}
```

Kernel performs only deterministic label matching.

It never contains:

```python
if admissibility == GM:
```

Unknown or malformed visibility fails closed.

Product authorization still happens outside DungeonMind. A client may not simply claim arbitrary labels without passing whatever authorization boundary its deployment requires.

### 3.2 Domain admission

Core admission remains non-configurable:

```text
exact revision identity
source/evidence validity
knowledge standing
scope
visibility
referential integrity
retraction/supersession
```

A domain may additionally narrow admission through a pinned pure policy.

It may never recover knowledge rejected by the Kernel.

Conceptual interface:

```text
DomainAdmissionPolicy
  validate_assertion(...)
  validate_source_annotation(...)
  evaluate_domain_constraints(...) -> ADMIT | EXCLUDE
```

Requirements:

- deterministic;
- pure;
- no storage access;
- no network access;
- no clock access;
- no graph mutation;
- identity pinned to `DomainContractRef`;
- may only narrow Kernel-admissible knowledge.

This avoids arbitrary plug-in hooks becoming authority.

---

## 4. Domain contract versus semantic profile

Do not collapse these into one abstraction.

They answer different questions.

### DomainContract

> What structural/domain policy applies to this knowledge space?

It defines:

```text
domain identity
scope axes
visibility labels
claim-mode requirements
temporal extension schemas
domain-metadata schemas
pure domain admission policy identity
source-annotation schemas
```

Example:

```text
dungeonbuddy.world / v1
```

### SemanticProfile

> Which ontology/vocabulary does this domain revision admit?

The current digest-pinned profile idea survives.

A v2 descriptor should grow beyond namespaces and declare validation-relevant term structure, for example:

```text
SemanticProfileDescriptorV2
  profile_id
  profile_revision
  descriptor_sha256

  term_namespaces

  predicates[
    term
    allowed_value_kinds
    literal_schema?
  ]

  classification_terms[]
```

The Kernel validates qualified terms through the pinned profile.

It does not understand their meaning.

Example:

```text
DomainContract:
  dungeonbuddy.world/v1

SemanticProfile:
  dungeonbuddy.dnd5e/v4
```

Later:

```text
DomainContract:
  rules.knowledge/v1

SemanticProfile:
  dnd2024.rules/v1
```

This preserves the existing useful profile concept without pretending profile identity alone is a full domain plug-in system.

---

## 5. Temporal contract

Current fictional-time structure is valuable but domain-specific.

vNext should use:

```text
TemporalScope
  kind:
    unknown
    timeless
    utc_interval
    domain_ref
```

For `utc_interval`:

```text
valid_from?
valid_until?
```

For `domain_ref`:

```text
schema: QualifiedTerm
payload: canonical JSON
```

DungeonBuddy fictional time becomes, for example:

```text
kind = domain_ref
schema = dungeonbuddy.time:fictional_anchor_v1
payload = {
  bundle_id,
  campaign_id,
  anchor_id
}
```

The DungeonBuddy domain contract validates that structure and its consistency with campaign scope.

A generic organizational memory system can instead express:

```text
valid_from = 2026-04-01
valid_until = 2026-09-07
```

The crucial distinction between **unknown** and **timeless** survives.

---

## 6. Source and evidence model

Sources should no longer be owned by a world.

A rulebook, policy document, meeting transcript, imported dataset, or email may support assertions in multiple spaces.

### SourceArtifact vNext

```text
SourceArtifact
  source_artifact_id
  source_classification: QualifiedTerm
  current_revision_id?
  authority: primary | derived | reference
  visibility: VisibilityRequirement
  status
  locator metadata
  foreign_refs[]
  domain_metadata[]
```

Removed from the generic contract:

```text
world_id
campaign_id
session_id
SourceDomain enum
GM/PLAYER Visibility enum
```

`source_domain_key` is the strongest existing precedent and should become the basis of `source_classification`.

`SourceRevision` remains substantially unchanged:

```text
source_revision_id
source_artifact_id
content_sha256
body_storage
locator
created_at
```

`EvidenceRole` remains Kernel-owned:

```text
support
contradiction
context
```

Those are generic evidence mechanics rather than TTRPG ontology.

Evidence refs remain exact pointers to artifact/revision/locator identity.

---

## 7. Contribution and write contract

The contribution lifecycle remains one of the core Kernel abstractions.

The vNext name may remain `GraphContribution` or move to `KnowledgeContribution`; this design recommends the latter because publication authority is no longer World-specific.

### KnowledgeContribution

```text
KnowledgeContribution
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

`producer` is provenance, not authority.

An agent writing about itself therefore uses exactly this path.

There is no privileged self-edit API.

### Typed contribution items

Replace the current bag of nullable/string fields with a discriminated union:

```text
ProposeEntity
  entity_id / provisional identity

ProposeAssertion
  assertion

RetractAssertion
  target_assertion_id

SupersedeAssertion
  target_assertion_id
  replacement_assertion

ProposeIdentityDecision
  identity proposal
```

Contribution processing produces explicit dispositions:

```text
accepted
rejected
unresolved
```

with identity outcomes and decision IDs where appropriate.

The accepted graph is still materialized only through governed publication.

The full lifecycle remains:

```text
producer/source
→ contribution
→ validation
→ identity resolution
→ item disposition
→ proposed revision
→ exact-parent validation
→ atomic CAS publication
→ durable receipt/recovery
```

---

## 8. Identity mechanics

Stable identity remains Kernel-owned.

Rename:

```text
object_id → entity_id
world_id  → space_id
```

Preserve values during migration.

Identity decisions become:

```text
IdentityDecision
  decision_id
  space_id
  decision_kind
  subject_entity_ids
  target_entity_ids
  actor
  reason
  reversible
  supersedes_decision_ids
  status
```

Merge, split, unmerge, ambiguity, rejection, and explicit override remain Kernel behavior.

Confidence remains non-authoritative.

### Existing relationship identities

Current v4+ relationships may possess both:

```text
relationship_id
assertion_metadata.assertion_id
```

vNext should not invent a third identity or silently drop one.

Decision:

- the existing assertion metadata `assertion_id` becomes the canonical vNext assertion identity where present;
- the old `relationship_id` is retained in the migration manifest as a legacy structural identity mapping;
- any persisted/external references to relationship IDs are migrated through that exact mapping during joint cutover;
- old immutable revisions retain the original relationship IDs;
- v1-v3 relationships without durable assertion IDs receive deterministic migration assertion IDs derived from exact legacy revision + relationship identity, and the mapping is sealed.

Do not place permanent `legacy_relationship_id` fields into the new assertion model merely to make migration convenient.

---

## 9. Proposed public read contract

```text
ProjectionRequest
  space_id
  revision_pin?
  scope_selector
  audience_labels
  standing_selector
  focus[]
  domain_context?
```

No:

```text
campaign_id
ScopeModeV2
Admissibility.GM
Admissibility.PLAYER
session-specific Kernel focus enum
```

The result identifies exactly what was read:

```text
ProjectionSnapshot
  space_id
  revision_id
  head_revision_id
  is_head
  domain_contract_ref
  semantic_profile_ref
  scope_selector
  audience_labels
  standing_selector
  focus
  projected_at
```

Retrieval operations remain recognizable:

```text
get_entity
get_complete_entity
search
neighborhood
get_evidence
resolve_source_anchor
```

but operate over generic entities/assertions.

A product-specific adapter may map:

```text
get_complete_entity
→ DungeonBuddy World Object card
```

without rebuilding authority.

---

## 10. Exact v1 → vNext breaking inventory

| Current contract | vNext disposition |
|---|---|
| `WorldGraphRevision` | `KnowledgeRevision`; `world_id → space_id`; pins DomainContract + SemanticProfile |
| `WorldGraphHead` | `KnowledgeHead`; one per `space_id` |
| `PublishRevisionCommand` | `PublishKnowledgeRevision`; same CAS invariant, `space_id` |
| `StoredGraphRevision` | `StoredKnowledgeRevision` |
| `WorldGraphProjectionRequestV2` | generic `ProjectionRequest` |
| `ProjectionSnapshotV2` | generic `ProjectionSnapshot` |
| `ScopeModeV2` | deleted; expressed by `ScopeSelector` |
| `campaign_id` | domain scope binding |
| `ProjectionFocus` / session-specific focus | qualified `FocusRef` |
| `Admissibility.GM/PLAYER` | effective audience labels + visibility requirements |
| `GraphContribution` / `GraphContributionV2` | `KnowledgeContribution` |
| contribution `world_id` | `space_id` |
| contribution `campaign_scope` | generic scope |
| contribution string `value` | discriminated `AssertionValue` |
| `GraphContributionAssertion` nullable relationship/attribute bag | typed assertion proposal |
| `KnowledgeAssertionMetadataV1.campaign_scope` | generic `ScopeSet` |
| `Visibility.GM/PLAYER` | qualified visibility labels |
| `EpistemicKindV2` | Kernel `EpistemicBasis` + domain `claim_mode` |
| `CanonState` | Kernel `KnowledgeStanding` |
| `session_refs` | DungeonBuddy domain metadata / source-event association |
| `TemporalScopeRefV1.FICTIONAL_TIME_REF` | generic `domain_ref` temporal scope |
| `SourceArtifact/V2.world_id` | removed |
| `SourceArtifact/V2.campaign_id` | domain annotation/scope association |
| `SourceArtifact/V2.session_id` | domain annotation/source-event association |
| `SourceDomain` | qualified source classification |
| source `Visibility.GM/PLAYER` | generic `VisibilityRequirement` |
| `SemanticProfileRef` | concept retained; v2 profile contract |
| `SemanticProfileDescriptor` namespaces-only | v2 descriptor with validation-relevant term specs |
| `IdentityDecisionRecord.world_id` | `space_id` |
| `subject_object_ids` | `subject_entity_ids` |
| `GraphObjectView` | generic `EntityView` |
| `GraphRelationshipView` | assertion with `EntityRefValue` |
| separate relationship evidence target | canonical assertion target after migration |
| World-specific service names | generic projection/retrieval services |
| v1-v6 union graph payloads | immutable legacy schemas; not rewritten |

This is intentionally source-breaking.

---

## 11. DungeonBuddy domain contract

DungeonBuddy owns a package/module implementing something equivalent to:

```text
DungeonBuddyWorldDomainContract
  domain_id = dungeonbuddy.world
```

It declares:

### Scope axes

```text
dungeonbuddy.scope:campaign
dungeonbuddy.scope:session   # only if session is actually an authority scope
```

### Visibility labels

```text
dungeonbuddy.visibility:player
dungeonbuddy.visibility:gm
```

### Claim modes

Examples:

```text
dungeonbuddy.claim:fact
dungeonbuddy.claim:belief
dungeonbuddy.claim:rumor
dungeonbuddy.claim:plan
dungeonbuddy.claim:observed_event
```

### Domain metadata schemas

Examples where still necessary:

```text
session provenance
fictional-time references
campaign lifecycle metadata
```

### Ontology

Through the semantic profile:

```text
NPC
PC
person
location
faction
encounter
quest
etc.
```

None is imported by DungeonMind core.

DungeonBuddy is also responsible for mapping an authorized product role to effective Kernel labels.

Example:

```text
PLAYER
→ [dungeonbuddy.visibility:player]

GM
→ [
     dungeonbuddy.visibility:player,
     dungeonbuddy.visibility:gm
   ]
```

The Kernel owns the enforcement. DungeonBuddy owns the meaning.

---

## 12. Persistence and migration strategy

Do **not** rewrite the existing immutable graph history.

Do **not** perform an in-place semantic column rename and declare migration complete.

Use a **bridge-genesis migration**.

### Phase A — freeze v1 authority

Select an exact v1 authority point:

```text
world_id
head revision_id
graph payload digest
source/evidence state digest
adoption/reviewed-init lineage
contribution set
identity-decision set
```

Create a deterministic migration manifest.

### Phase B — create the vNext space

```text
space_id = exact old world_id value
```

No new world/entity IDs merely because the schema changed.

### Phase C — translate current committed meaning

Produce one initial vNext revision:

```text
K0
parent_revision_id = null
migration_origin_ref = {
  legacy_schema,
  legacy_world_id,
  legacy_head_revision_id,
  legacy_graph_payload_sha256,
  migration_manifest_sha256
}
```

This is **not** pretending the v1 head was a native vNext parent.

It is an explicit authority bridge.

### Phase D — preserve IDs

Preserve exactly where possible:

```text
entity/object IDs
assertion IDs
evidence IDs
source artifact IDs
source revision IDs
contribution IDs
identity decision IDs
```

Relationship structural IDs receive explicit deterministic mappings as described above.

### Phase E — preserve old history

All old revisions remain immutable and readable through the frozen historical reader.

They are not transformed in place.

The current vNext API does not need to pretend old payloads are native vNext.

Historical compatibility may remain in a quarantined `compat.v1` reader because there is a named reconstructibility obligation.

It is not part of the new current-write architecture.

### Phase F — semantic equality

Migration is accepted only when:

```text
v1 authority
→ current DungeonBuddy semantic normalization

equals

vNext K0
→ DungeonBuddy vNext domain contract
→ same normalization
```

Differences caused merely by renamed transport fields are normalized away.

Knowledge meaning, scope, visibility, evidence, temporal semantics, and identity are not.

---

## 13. Parallel DungeonMind / DungeonBuddy implementation boundary

Do not implement this as “Kernel first, adapters later.”

Use one frozen contract revision.

```text
              vNext contract package
               /               \
              /                 \
DungeonMind implementation    DungeonBuddy domain implementation
              \                 /
               \               /
            joint acceptance fixture
                     |
                 migration
                     |
                  cutover
```

### Contract-first slice

Before behavior code:

```text
DomainContractRef
SemanticProfileDescriptorV2
ScopeBinding / ScopeSelector
VisibilityRequirement
TemporalScope
Entity
Assertion / AssertionValue
AssertionMetadata
KnowledgeContribution
KnowledgeRevision / KnowledgeHead
ProjectionRequest / ProjectionSnapshot
migration manifest schema
```

Generate/check in JSON schemas or equivalent canonical contract fixtures.

Both repositories pin the exact contract revision/digest.

Neither side invents missing fields independently.

### DungeonMind implementation

Owns:

```text
storage
canonical serialization
revision/head
CAS
contributions
identity
evidence
generic scope
generic visibility
generic retrieval
domain contract registry
policy execution boundary
```

### DungeonBuddy implementation

Owns:

```text
TTRPG domain contract
D&D semantic profile
campaign/session mapping
GM/player label mapping
fictional time adapter
source classifications
World-object DTO adaptation
Plan / Build / Play use
```

---

## 14. Cross-side acceptance contract

Create one canonical machine-readable artifact:

```text
dm_vnext_contract_acceptance_v1.json
```

It records:

```text
DungeonMind commit
DungeonBuddy commit
contract schema digest
domain-contract digest
semantic-profile digest
migration-manifest digest
fixture digests
projection/result semantic digests
```

Acceptance has three required fixture families.

### A. DungeonBuddy preservation fixture

Use the existing governed campaign corpus/witness semantics.

Must prove:

```text
space/global knowledge
campaign C2 scope
cross-campaign scope
GM visibility
PLAYER visibility
session focus
entity classification
relationships
assertion ledger
evidence
anchors
fictional-time metadata
head and historical revision behavior
contribution publication
```

Existing campaign semantics must survive even though the generic Kernel no longer knows what campaign or GM means.

### B. Organizational-memory fixture

Minimum entities:

```text
Priya
Marco
Retrieval Evaluation
Research Team
ownership document
```

Required history:

```text
Priya owns Retrieval Evaluation
valid 2026-04-01 → 2026-09-07

Marco owns Retrieval Evaluation
valid from 2026-09-07

Priya member_of Research Team
Marco member_of Research Team
```

Must prove:

- no fictional/TTRPG vocabulary is needed by Kernel;
- temporal change is additive rather than overwrite;
- evidence binds to documents;
- project/team scope works;
- exact historical revision reconstructs the earlier owner.

### C. Epistemic/adversarial fixture

Must contain:

```text
conflicting claims
belief versus established fact
rumor
plan
retraction
two ambiguous identity candidates
merge or split + reversal
restricted visibility
multiple independent evidence supports
historical replay
```

Required proof:

> Generality did not flatten governance.

---

## 15. Required decisions resolved

| Question | Decision |
|---|---|
| Generic durable root? | `KnowledgeSpace`; one head + immutable lineage |
| Generic scope? | qualified `ScopeBinding` + deterministic `ScopeSelector` |
| Kernel entity kinds? | none; classifications are domain-qualified knowledge |
| Predicate validation? | pinned `SemanticProfileDescriptorV2` predicate specs |
| Universal epistemics? | `asserted/inferred/speculative` derivation basis |
| Domain epistemics? | required qualified `claim_mode` such as fact/belief/plan |
| Generic visibility? | Public / LabelsAny / LabelsAll |
| GM/player meaning? | DungeonBuddy-owned label vocabulary and role mapping |
| Domain admissibility? | pinned pure policy may only narrow Kernel-admissible facts |
| Generic projection? | revision + generic scope + visibility + standing + focus |
| Current schemas break? | graph, projection, contribution, assertion metadata, source, identity, public views |
| Durable migration? | deterministic bridge-genesis from exact v1 authority point |
| Preserve entity IDs? | yes |
| Mutate v1 revisions? | never |
| Parallel implementation? | both repos implement one frozen contract digest |
| Final alignment proof? | joint `dm_vnext_contract_acceptance_v1.json` |

---

## 16. Deletion plan for obsolete v1 concepts

After joint cutover, delete from the **current public surface**:

```text
WorldGraphRevision
WorldGraphHead
WorldGraphProjectionRequestV2
ProjectionSnapshotV2
ScopeModeV2
Admissibility.GM / PLAYER
campaign_scope in Kernel contracts
Kernel SourceDomain TTRPG vocabulary
Kernel fictional-time dependency
World-specific application service names
relationship as a separate authority record
old current-write GraphContribution shapes
```

Do not delete historical reconstruction merely because the current API moved on.

The sequence is:

```text
1. Freeze vNext contract.
2. Implement DungeonMind vNext.
3. Implement DungeonBuddy domain contract concurrently.
4. Migrate sealed authority into bridge K0.
5. Pass all three contract fixtures.
6. Pass migrated DungeonBuddy semantic equivalence.
7. Freeze v1 writes.
8. Joint cutover.
9. Remove v1 current/public services and imports.
10. Quarantine old schemas/readers under historical compatibility.
11. Delete physical legacy storage only under a later explicit reconstructibility proof.
```

No long-lived dual-write system.

No indefinite v1/vNext current API pair.

---

## 17. Risks

### Domain contract becomes an arbitrary plug-in system

Mitigation: durable descriptors are data-only; executable policy has one narrow pure interface and may only exclude, never override Kernel integrity.

### Scope model becomes too weak

The proposed axis/value model intentionally covers known cases without inventing a policy language.

If a future domain needs hierarchy, the domain may expand its authorized context into effective bindings before the Kernel match.

Do not add arbitrary scope expressions until a real domain requires them.

### Scope model becomes ACL machinery

Visibility and scope remain separate.

Scope answers:

> what context does this knowledge apply to?

Visibility answers:

> which authorized audience labels may observe it?

Do not conflate them.

### Semantic profiles become ontologies plus executable behavior

Keep vocabulary validation in SemanticProfile and policy behavior in DomainContract.

### Migration creates new identity accidentally

Every new ID must appear in the migration manifest with a reason.

Changing a Python type name is never sufficient reason to mint a new durable entity ID.

### Sources become duplicated per space

vNext deliberately removes mandatory space ownership from source identity.

Evidence connects a source to knowledge in a space.

### Genericity weakens epistemics

Prevented by retaining mandatory:

```text
epistemic basis
claim mode
standing
temporal state
visibility
scope
evidence
```

Generality comes from qualified domain terms, not missing metadata.

---

## 18. Rejected alternatives

### Rename `world_id` to `space_id` and keep everything else

Rejected.

That preserves campaign, GM/player, canon, session, and fictional-time assumptions under generic names.

### Untyped property graph

Rejected.

`predicate: str` plus arbitrary JSON with no pinned domain validation would make semantic integrity unenforceable.

### Move all policy to DungeonBuddy

Rejected.

Evidence integrity, revision identity, contribution governance, generic scope enforcement, visibility enforcement, standing, and replay are Kernel responsibilities.

### Make all domain concepts Kernel enums

Rejected.

That simply recreates the existing problem with a larger ontology.

### Put executable callbacks in semantic-profile JSON

Rejected.

Pinned data identity is valuable precisely because it is not arbitrary code execution.

### Keep GM/PLAYER as “generic enough”

Rejected.

They are excellent DungeonBuddy concepts and bad generic Kernel concepts.

### One graph per campaign/project/team

Rejected.

Scope remains knowledge metadata inside one authority space.

### Rewrite every old immutable revision as vNext

Rejected.

That destroys the distinction between historical truth and migration output.

### Permanent v1 adapter layer in the new architecture

Rejected.

Compatibility exists only where a named historical/migration consumer requires it and is quarantined from current contracts.

### Silent self-mutation by agents/entities

Rejected.

The active entity/agent is producer provenance. Writes remain contributions.

---

## 19. Remaining implementation-level decisions

The conceptual contract is sufficiently resolved to prototype, but these should be answered by focused implementation design rather than guessed in the architecture:

1. Physical PostgreSQL migration should choose new vNext tables versus versioned records in existing tables based on rollback and query-cost evidence. The semantic migration must not depend on that choice.
2. Exact packaging of the frozen historical reader (`dungeonmind.compat.v1` versus separate package/tool) should follow the named historical consumers.
3. The first `SemanticProfileDescriptorV2` predicate-spec representation should remain deliberately narrow; JSON Schema, a smaller internal value schema, or generated Pydantic metadata are implementation choices provided they are digest-pinned and deterministic.
4. Broader source-authority snapshot identity remains a separate issue from graph-revision identity. vNext must not falsely claim that a graph revision alone freezes later mutable source lifecycle state.

None of these require putting campaign semantics back in Kernel.

---

## 20. Architectural invariant

The vNext architecture succeeds only when both statements hold:

> DungeonMind can durably represent, govern, revise, reconcile, and project knowledge about an arbitrary domain without understanding that domain's ontology.

And:

> DungeonBuddy recovers its existing campaign semantics through an explicit domain contract and semantic profile, without weakening provenance, epistemic state, temporal state, visibility, contribution governance, identity reconciliation, immutable history, or CAS publication.

The shortest useful description of the resulting boundary is:

```text
DungeonMind knows
  what identity is,
  what an assertion is,
  what evidence is,
  what a revision is,
  and how governed knowledge changes.

DungeonBuddy knows
  what the assertions mean.
```

---

## Next implementation-design slice

Do not begin with a giant Kernel rewrite.

The next slice should be a contract-only handoff that turns sections 1–9 into exact schemas/types plus the three acceptance fixtures, with no storage migration or DungeonBuddy cutover behavior yet.

That contract must be concrete enough for DungeonMind and DungeonBuddy to implement concurrently without independently inventing the missing semantics.