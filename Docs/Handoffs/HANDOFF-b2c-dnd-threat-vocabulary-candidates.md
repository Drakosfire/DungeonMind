# HANDOFF — B.2c DungeonMindDnD Threat Vocabulary and Extraction Candidate Contract

**Created:** 2026-08-01
**Status:** ACTIVE — dispatch exactly one DungeonMind-owned capability.
**Canonical handoff path:** `Docs/Handoffs/HANDOFF-b2c-dnd-threat-vocabulary-candidates.md`
**Repository:** Drakosfire/DungeonMind
**Suggested branch:** `founding/pr-b2c-dnd-threat-vocabulary-candidates`
**Implementation base:** `9d9d8cc1b9fefe9c9cc6bfad5e3d0d6932645e0e`
**Predecessor:** merged PR `#7` — B.2b versioned semantic-profile boundary and DungeonMindDnD extraction
**Suggested PR title:** B.2c: DungeonMindDnD Threat vocabulary and extraction candidates
**One-line mission:** Make `dungeonmind_dnd` the first executable semantic-profile package by defining one narrow, versioned Threat-oriented D&D vocabulary, typed provenance-bearing extraction candidates, and deterministic validation—without teaching the DungeonMind kernel D&D semantics, calling an LLM, publishing a graph, or modeling mechanics.

---

## §0 Capability decomposition decision

B.2b established the permanent seam:

```text
DungeonMind kernel
  owns identity, evidence, revisions, retrieval, admission, and projection

DungeonMindDnD
  owns D&D semantic meaning behind an exact profile identity
```

The next PR must exercise the D&D-owned side of that seam without immediately constructing the generic ontology/taxonomy interpretation layer that the seam was designed to postpone.

### Selected capability

```text
D&D profile revision v2
→ exact, package-owned Threat vocabulary catalog
→ typed extraction candidate packet
→ deterministic term, relationship, endpoint, and evidence validation
→ deterministic prompt/schema material for a future extractor
→ synthetic Threat candidate fixture that connects new candidates to an existing node
```

### Why this is one capability

The vocabulary, candidate schema, validator, and prompt/schema material all establish one useful result:

A future LLM extractor or human author can propose D&D Threat-shaped graph candidates using one controlled vocabulary and receive deterministic validation before identity resolution, review, contribution planning, or graph publication.

A vocabulary file without a consumer contract is documentation. A candidate schema without a controlled vocabulary permits predicate and kind drift. A prompt fragment without deterministic validation makes the prompt the authority. These pieces therefore land together.

### Explicitly rejected for this slice

| Alternative | Decision | Reason |
| --- | --- | --- |
| Add D&D kinds/predicates to `src/dungeonmind` | Reject | Reverses the B.2b ownership boundary |
| Add a generic term registry to the kernel | Defer | No second-system evidence; would begin the interpretation layer prematurely |
| Make Threat an object kind | Reject | Threat is contextual/product meaning, not stable identity |
| Add statblock, AC, HP, CR, creature type, spells, or conditions | Reject | Mechanics and classification are independently useful successors |
| Call an LLM | Reject | This PR defines and validates the contract; it does not choose a provider or prompt runtime |
| Resolve candidate identity | Reject | Stable identity and merge decisions require graph context and review policy |
| Publish graph revisions | Reject | Candidate-to-contribution and contribution-to-publication are separate capabilities |
| Add properties as an open JSON bag | Reject | Recreates the universal WorldObject failure mode |
| Support multiple systems | Reject | The point is to learn the D&D side concretely first |
| Add taxonomy inheritance or ontology reasoning | Reject | Not required to constrain one extraction slice |
| Put campaign prose or rulebook text in the repository | Reject | Fixtures must remain synthetic and license/PII safe |

### Governing invariant

The DungeonMind kernel remains completely unaware of the D&D vocabulary.
DungeonMindDnD may depend one-way on narrow public DungeonMind contracts, but
the kernel may never import DungeonMindDnD. Every candidate is provenance-
bearing, non-canonical, and non-publishable. Threat is represented by a
contextual `dnd5e:threatens` relationship, never by `kind = dnd5e:threat`.

### Mission falsification test

This is no longer one PR if it requires a graph schema change, a database
migration, a DungeonMind reader change, graph publication, identity resolution,
an LLM/provider integration, a statblock/mechanics model, a generic ontology
interpreter, a product surface, or a second production game system.

## §1 Outcome

After this PR, `dungeonmind_dnd` is no longer merely a descriptor carrier. It is a profile-owned, side-effect-free Python package that can:

- load one immutable D&D semantic profile revision and one immutable Threat vocabulary catalog from package data;
- expose strict, versioned candidate contracts suitable for structured LLM output or human-authored JSON;
- render deterministic JSON Schema and a controlled-vocabulary prompt fragment;
- validate candidate kinds and predicates against the catalog;
- validate relationship direction/domain/range;
- validate a closed evidence ledger;
- represent endpoints as either new candidates or explicit existing graph-object references;
- reject dangling endpoints, predicate drift, foreign namespaces, duplicate IDs, ungrounded candidates, and attempts to encode Threat as an object kind;
- produce no stable object IDs, merge decisions, graph contributions, or durable writes.

The proof fixture uses a synthetic D&D threat scenario:

```text
new creature candidate: Tripod Null-Calf
new encounter candidate: North Gate Breach
existing location reference: obj:north-gate
relationships:
  Tripod Null-Calf dnd5e:located_at North Gate
  Tripod Null-Calf dnd5e:participates_in North Gate Breach
  Tripod Null-Calf dnd5e:threatens North Gate
```

The fixture proves that candidate production can connect to an existing node without claiming that the candidate pipeline resolves identity or has read authority over the graph.

## §2 Why this is the next slice

PR #7 merged `dm_union_graph_v3`, exact semantic-profile pinning, namespace-qualified kinds and predicates, and a one-way `dungeonmind_dnd` package boundary. It deliberately left the D&D package data-only and left concrete D&D semantics false.

The next useful learning target is not a universal interpretation framework. It is whether a narrow D&D vocabulary can reliably constrain extraction.

The project's graph-construction research identifies the dominant failures as:

- schema drift
- cross-class collisions
- predicate drift
- inverted relationships
- dangling or hallucinated edges
- weak provenance
- premature identity merging

The recommended minimal sequence is:

```text
schema-guided packet
→ typed node/edge candidates
→ deterministic validation
→ exact candidate blocking / identity work
→ reviewable upsert or contribution planning
→ publication
```

B.2c owns only the first three steps.

This PR also turns a product insight into a concrete semantic decision:

> A creature can threaten a location now and cease threatening it later.
> Therefore "Threat" is a contextual relationship/workflow role, not the
> creature's ontological kind.

That decision keeps the future system capable of representing the same creature as an enemy, neutral actor, ally, captive, summoned participant, or historical entity without rewriting its identity.

## §3 Authority, base, and required reading

### Repository-state gate

Before editing:

```bash
git fetch origin
git checkout main
git pull --ff-only
git rev-parse HEAD
```

Expected base: `9d9d8cc1b9fefe9c9cc6bfad5e3d0d6932645e0e` (merge commit for PR #7).

If main has moved, inspect every intervening DungeonMind PR for changes to: `src/dungeonmind_dnd/`; semantic profile descriptors or registry behavior; graph schemas; evidence contracts; import boundaries; roadmap/architecture ownership; any candidate, extraction, ontology, taxonomy, Threat, or statblock work. Stop if another merged or open PR already owns this capability.

### Read in this order

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE.md`
3. `Docs/Decisions/ADR-0004-semantic-profile-boundary.md`
4. `Docs/Roadmaps/ROADMAP.md`
5. `CONTRIBUTING.md`
6. `Docs/Handoffs/HANDOFF-b2b-semantic-profile-boundary.md`
7. PR #7 handback and merge commit
8. `src/dungeonmind/contracts/base.py`
9. `src/dungeonmind/contracts/evidence.py`
10. `src/dungeonmind/contracts/semantic_profile.py`
11. `src/dungeonmind/domain/canonical.py`
12. `src/dungeonmind_dnd/__init__.py`
13. `src/dungeonmind_dnd/profiles/dnd5e-v1.json`
14. `tests/unit/test_import_boundaries.py`
15. `pyproject.toml`
16. Project Source `LLM-graph-construction.md`, especially the candidate-contract and minimal-pipeline sections

### Authority precedence

1. Current checked-in DungeonMind contracts, ADRs, architecture, and code
2. Merged repository state at `9d9d8cc1...`
3. This checked-in handoff
4. Existing tests and synthetic fixtures
5. `LLM-graph-construction.md` as design/research evidence
6. DungeonMindBuddy Threat/statblock documents as consumer requirements only
7. Chat summaries

DungeonMindBuddy documents do not authorize putting D&D semantics into the kernel. They may justify which narrow profile-owned terms are needed.

## §4 Ownership boundary after this PR

### DungeonMind kernel continues to own

- strict shared contract base
- evidence/source contracts
- semantic-profile identity and descriptor contracts
- canonical JSON hashing
- graph identity, revisions, retrieval, admission, and projection
- capability policy

No kernel runtime behavior changes in this PR.

### DungeonMindDnD begins to own executable profile behavior

- D&D profile revision v2
- D&D Threat vocabulary catalog
- D&D candidate packet contracts
- D&D relationship domain/range rules
- D&D candidate validation
- D&D prompt/schema rendering
- D&D synthetic conformance fixtures

### One-way dependency rule

After this PR:

```text
dungeonmind_dnd
  may import:
    dungeonmind.contracts.base
    dungeonmind.contracts.evidence
    dungeonmind.contracts.semantic_profile
    dungeonmind.domain.canonical
    stdlib
    pydantic

dungeonmind_dnd
  may not import:
    dungeonmind.application
    dungeonmind.infrastructure
    dungeonmind.service
    dungeonmind.agents
    dungeonmind repositories
    FastAPI
    PostgreSQL/pgvector
    model/provider SDKs

dungeonmind
  may never import dungeonmind_dnd
```

This deliberately evolves the B.2b phrase "data-only package" into: **profile-owned, side-effect-free package with contracts and pure deterministic application logic.** The package still performs no registration, configuration discovery, network access, database access, or durable write on import.

### Extraction portability rule

All `dungeonmind_dnd` executable code must remain movable to another distribution later without changing: semantic profile IDs; descriptor bytes/digests; vocabulary IDs/revisions/digests; candidate schema versions; serialized candidate packet shapes.

## §5 Semantic profile revision

Do not modify `src/dungeonmind_dnd/profiles/dnd5e-v1.json` — it is an immutable published profile descriptor.

Create `src/dungeonmind_dnd/profiles/dnd5e-v2.json`:

```json
{
  "schema_version": "dm_semantic_profile_v1",
  "profile_id": "dungeonmind.dnd5e",
  "profile_revision": "dnd5e-profile-v2",
  "term_namespaces": ["dnd5e"]
}
```

Why a new profile revision is required: v1 proved namespace ownership only; v2 becomes the exact profile identity associated with the first concrete D&D vocabulary; old v1 graphs and descriptors remain readable; no descriptor is edited in place; the kernel descriptor schema remains unchanged.

The D&D vocabulary catalog must pin the complete `SemanticProfileRef` for v2, including the canonical descriptor digest. The example registry configuration must retain v1 and add v2. It must not replace v1.

## §6 Threat vocabulary catalog

Create `src/dungeonmind_dnd/vocabularies/threat-v1.json`. Schema: `dmdnd_semantic_vocabulary_v1`.

Conceptual shape:

```json
{
  "schema_version": "dmdnd_semantic_vocabulary_v1",
  "vocabulary_id": "dungeonmind.dnd5e.threat",
  "vocabulary_revision": "threat-v1",
  "semantic_profile": {
    "schema_version": "dm_semantic_profile_ref_v1",
    "profile_id": "dungeonmind.dnd5e",
    "profile_revision": "dnd5e-profile-v2",
    "descriptor_sha256": "<canonical digest of dnd5e-v2.json>"
  },
  "object_kinds": [
    {
      "term": "dnd5e:creature",
      "label": "Creature",
      "description": "A persistent creature or character identity in the campaign world."
    }
  ],
  "predicates": [
    {
      "term": "dnd5e:located_at",
      "label": "Located at",
      "description": "Places a subject at a campaign location.",
      "subject_kinds": ["dnd5e:creature", "dnd5e:encounter"],
      "object_kinds": ["dnd5e:location"]
    }
  ]
}
```

### Exact v1 object-kind inventory

`dnd5e:creature`, `dnd5e:location`, `dnd5e:faction`, `dnd5e:encounter`

| Term | Meaning in this profile |
| --- | --- |
| `dnd5e:creature` | A persistent creature or character identity. This does not imply NPC, enemy, ally, monster type, or statblock availability. |
| `dnd5e:location` | A campaign place that can be referenced by identity. |
| `dnd5e:faction` | A persistent organized group or affiliation. |
| `dnd5e:encounter` | A bounded prepared, potential, historical, or active play situation. It is not synonymous with combat. |

### Exact v1 predicate inventory

`dnd5e:located_at`, `dnd5e:member_of`, `dnd5e:participates_in`, `dnd5e:threatens`

| Predicate | Subject kinds | Object kinds | Semantic intent |
| --- | --- | --- | --- |
| `dnd5e:located_at` | creature, encounter | location | Subject is situated at the location for the asserted context. |
| `dnd5e:member_of` | creature | faction | Creature is affiliated with the faction. |
| `dnd5e:participates_in` | creature, faction | encounter | Subject participates in the encounter. |
| `dnd5e:threatens` | creature, faction, encounter | location, faction, creature | Subject poses a contextual threat to the object. |

### Deliberate exclusions

Do not add these terms in v1: `dnd5e:threat`, `dnd5e:npc`, `dnd5e:monster`, `dnd5e:item`, `dnd5e:spell`, `dnd5e:condition`, `dnd5e:statblock`, `dnd5e:mechanics_resource`, `dnd5e:creature_type`, `dnd5e:encounter_role`, `dnd5e:allied_with`, `dnd5e:enemy_of`, `generic:*`, `ttrpg:*`.

Rationale: Threat is contextual and represented by `dnd5e:threatens`. NPC, monster, enemy, and ally are roles or classifications, not identity kinds in this first slice. Mechanics and classification require independently evidence-scoped semantics not present in this candidate contract. Generic cross-system terms would pre-design the future interpretation layer.

### Catalog invariants

- exact schema literal;
- exact vocabulary ID and revision;
- exact pinned profile ref;
- unique terms;
- all terms use the pinned profile's `dnd5e` namespace;
- categories are disjoint;
- predicate subject/object kinds exist in the same catalog;
- descriptions are metadata for humans/prompts, not graph truth;
- catalog content is immutable at one revision;
- any term, direction, range, label, or description change creates a new vocabulary revision;
- catalog digest uses DungeonMind canonical JSON hashing.

## §7 Candidate contracts

Create `src/dungeonmind_dnd/contracts/vocabulary.py` and `src/dungeonmind_dnd/contracts/candidates.py`. All models inherit `DungeonMindModel` and remain `extra="forbid"`.

### §7.1 DndVocabularyRef

Schema: `dmdnd_vocabulary_ref_v1`. Fields: `vocabulary_id`, `vocabulary_revision`, `catalog_sha256`.

Rules: exact non-floating identity; 64-character lowercase digest; no path, URI, module, or `latest`; no config locator.

### §7.2 DndCandidateEndpointRef

Exactly one target form: `{"candidate_id": "cand:tripod-null-calf"}` or `{"existing_object_id": "obj:north-gate", "expected_kind": "dnd5e:location"}`.

Rules: exactly one of `candidate_id` / `existing_object_id`; candidate reference must resolve within the packet; existing object reference must carry `expected_kind`; `expected_kind` must be in the vocabulary; the package does not verify that the external graph object actually exists or has that kind — that check belongs to later graph-aware resolution/contribution planning; endpoint refs never contain labels, aliases, summaries, or copied graph objects.

### §7.3 DndNodeCandidate

Schema: `dmdnd_node_candidate_v1`. Fields: `candidate_id`, `kind`, `label`, `surface_forms`, `summary`, `evidence_ref_ids`.

Rules: `candidate_id` is temporary candidate identity, not graph identity; candidate IDs are unique within the packet; candidate IDs must not begin with `obj:` or `rel:`; `kind` must be an exact object-kind term from the pinned catalog; label is non-empty; surface forms are ordered, non-empty, normalized-unique aliases/mentions; label need not be duplicated in surface forms; summary is optional and non-empty when present; every candidate has at least one evidence reference; no arbitrary properties; no confidence score; no stable object ID; no canon state; no visibility field (visibility is carried by source/evidence authority in the kernel contracts).

### §7.4 DndRelationshipCandidate

Schema: `dmdnd_relationship_candidate_v1`. Fields: `candidate_id`, `subject`, `predicate`, `object`, `evidence_ref_ids`.

Rules: relationship candidate IDs are unique and distinct from node candidate IDs; predicate must be exact and catalog-owned; subject/object endpoint kinds must satisfy catalog domain/range; no inverse-predicate normalization; no arbitrary properties; every relationship has at least one evidence reference; a relationship cannot point to itself through the same candidate/existing reference; no stable relationship ID.

### §7.5 DndThreatCandidatePacket

Schema: `dmdnd_threat_candidate_packet_v1`. Fields: `schema_version`, `packet_id`, `world_id`, `campaign_id`, `semantic_profile`, `vocabulary`, `source_artifact_id`, `source_revision_id`, `focus_evidence_ref_ids`, `evidence_refs`, `nodes`, `relationships`.

Rules: exact profile ref must equal the catalog's pinned profile; exact vocabulary ref/digest must equal the loaded catalog; packet IDs are unique per extraction attempt but not durable graph IDs; packet may be world-scoped or campaign-scoped; evidence refs form a closed ledger (every referenced evidence ID exists exactly once in `evidence_refs`; no unused evidence refs); source artifact/revision fields agree with the packet source anchor where populated; every endpoint resolves to either a packet candidate or an explicitly typed existing object reference; every candidate node participates in at least one relationship or is the explicit focus candidate; at least one `dnd5e:threatens` relationship exists; no node kind named or aliased as `dnd5e:threat`; no relationship is silently inverted; packet is non-canonical and non-publishable by construction.

### Candidate packet does not contain

raw model output; chain of thought; confidence; token usage; provider identity; prompt text; stable object IDs for new candidates; identity outcome; merge decision; graph revision ID; contribution ID; publication capability; statblock or mechanics body.

Provider/run diagnostics may exist later in an extraction-run envelope. They do not belong in the semantic candidate contract.

## §8 Pure profile-side application logic

Create `src/dungeonmind_dnd/application/threat_candidates.py`.

Required pure functions:

```python
load_builtin_threat_vocabulary() -> DndSemanticVocabulary
builtin_threat_vocabulary_ref() -> DndVocabularyRef
threat_candidate_json_schema() -> dict[str, object]
render_threat_vocabulary_prompt() -> str
validate_threat_candidate_packet(
    packet: DndThreatCandidatePacket,
    vocabulary: DndSemanticVocabulary | None = None,
) -> DndThreatCandidatePacket
```

### Behavior

- package data is loaded with `importlib.resources`;
- no environment variables; no network; no database; no graph repository;
- no registration side effects; no import-time file read; no LLM;
- JSON Schema is deterministic;
- prompt fragment is deterministic and generated only from the catalog;
- the prompt fragment lists exact allowed kinds, exact allowed predicates, direction/range, and the rule that Threat is a relationship rather than a kind;
- prompt fragment contains no campaign prose or rulebook text;
- validator fails with D&D-package-owned typed errors or Pydantic validation errors;
- errors identify candidate IDs/term IDs but do not echo source prose.

### Error types

Create package-owned typed errors: `DndVocabularyIntegrityError`, `DndCandidateValidationError`. Do not add D&D error types to `src/dungeonmind/domain/errors.py`. The errors must remain usable without FastAPI or a service host.

## §9 Synthetic conformance fixture

Create `tests/fixtures/dungeonmind_dnd/tripod-null-calf-threat-candidates-v1.json`.

The fixture may use the names: Tripod Null-Calf; North Gate; North Gate Breach. All supporting prose must be synthetic, short, and license/PII safe.

Required candidate structure:

```text
candidate node: cand:tripod-null-calf, kind dnd5e:creature
candidate node: cand:north-gate-breach, kind dnd5e:encounter
existing endpoint: obj:north-gate, expected_kind dnd5e:location
relationships:
  Tripod Null-Calf located_at North Gate
  Tripod Null-Calf participates_in North Gate Breach
  Tripod Null-Calf threatens North Gate
```

Required evidence structure: at least one evidence ref per node; at least one evidence ref per relationship; a closed packet evidence ledger; synthetic `fixture://` locators; no statblock data; no AC/HP/CR; no creature type; no mechanics binding.

The fixture proves: controlled term use; correct predicate direction; provenance closure; new candidate to existing object connection; Threat as relationship; no stable identity assignment for new candidates.

## §10 Deterministic validation matrix

| Case | Expected result |
| --- | --- |
| Valid fixture | Accepted unchanged |
| kind = `dnd5e:threat` | Reject |
| Foreign namespace | Reject |
| Unknown D&D term | Reject |
| `located_at` inverted | Reject |
| `member_of` points to location | Reject |
| `participates_in` points to faction | Reject |
| `threatens` valid creature → location | Accept |
| Candidate endpoint missing | Reject |
| Existing endpoint lacks expected kind | Reject |
| Existing endpoint uses unknown expected kind | Reject |
| Duplicate candidate ID | Reject |
| Candidate ID begins `obj:` | Reject |
| Duplicate normalized surface form | Reject |
| Node without evidence | Reject |
| Relationship without evidence | Reject |
| Dangling evidence ID | Reject |
| Unused evidence ref | Reject |
| Profile ref differs from catalog | Reject |
| Catalog digest differs from packet ref | Reject |
| No threatens relationship | Reject |
| Open properties field supplied | Reject via strict model |
| Confidence supplied | Reject via strict model |
| Stable object ID supplied for a new candidate | Reject via strict model |

Property-based testing is not required. Exact table-driven tests are sufficient.

## §11 Import-boundary evolution

Modify `tests/unit/test_import_boundaries.py`. Replace the "stays data-only" rule with a narrower executable-profile rule.

Required assertions:

- `src/dungeonmind/**/*.py` never imports `dungeonmind_dnd`;
- `src/dungeonmind_dnd/**/*.py` may import only: `dungeonmind.contracts.base`, `dungeonmind.contracts.evidence`, `dungeonmind.contracts.semantic_profile`, `dungeonmind.domain.canonical`;
- `src/dungeonmind_dnd/**/*.py` may not import: `dungeonmind.application`, `dungeonmind.infrastructure`, `dungeonmind.service`, `dungeonmind.agents`, optional provider/database/API dependencies.

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
import dungeonmind_dnd
for forbidden in ("fastapi", "psycopg", "sqlalchemy", "openai", "anthropic"):
    assert forbidden not in sys.modules
PY
```

Importing `dungeonmind_dnd` must not load package data automatically. Resource reads occur only when a loader function is called.

## §12 Files in scope — exact allowlist

| Action | Path | Purpose |
| --- | --- | --- |
| Create | `Docs/Handoffs/HANDOFF-b2c-dnd-threat-vocabulary-candidates.md` | Canonical implementation handoff |
| Create | `Docs/Decisions/ADR-0005-dnd-profile-executable-boundary.md` | Executable profile-package and Threat semantics decision |
| Modify | `Docs/Architecture/ARCHITECTURE.md` | Profile-side candidate layer and ownership |
| Modify | `Docs/Architecture/AUTHORITY.md` | D&D catalog/candidate authority |
| Modify | `Docs/Roadmaps/ROADMAP.md` | B.2b landed; B.2c current; named successors |
| Modify | `README.md` | Repository/package status and truthful non-goals |
| Modify | `CONTRIBUTING.md` | One-way executable profile rules |
| Modify | `pyproject.toml` | Package data for v2 descriptor and vocabulary |
| Modify | `examples/semantic_profiles/registry.json` | Retain v1 and add v2 descriptor |
| Modify | `examples/semantic_profiles/README.md` | Explain v1/v2 coexistence and profile-owned vocabulary |
| Modify | `src/dungeonmind_dnd/__init__.py` | Side-effect-free package API and truthful package role |
| Create | `src/dungeonmind_dnd/contracts/__init__.py` | Contract exports |
| Create | `src/dungeonmind_dnd/contracts/vocabulary.py` | Catalog and vocabulary-ref contracts |
| Create | `src/dungeonmind_dnd/contracts/candidates.py` | Candidate packet contracts |
| Create | `src/dungeonmind_dnd/domain/__init__.py` | Package-owned errors |
| Create | `src/dungeonmind_dnd/domain/errors.py` | Typed D&D vocabulary/candidate errors |
| Create | `src/dungeonmind_dnd/application/__init__.py` | Pure application exports |
| Create | `src/dungeonmind_dnd/application/threat_candidates.py` | Load/render/validate functions |
| Create | `src/dungeonmind_dnd/profiles/dnd5e-v2.json` | Immutable profile revision for concrete vocabulary |
| Create | `src/dungeonmind_dnd/vocabularies/threat-v1.json` | Exact term catalog |
| Create | `tests/fixtures/dungeonmind_dnd/tripod-null-calf-threat-candidates-v1.json` | Synthetic proof packet |
| Create | `tests/unit/test_dnd_threat_vocabulary.py` | Catalog/profile/digest proof |
| Create | `tests/unit/test_dnd_threat_candidates.py` | Candidate validation matrix |
| Create | `tests/unit/test_dnd_threat_prompt_schema.py` | Deterministic schema/prompt proof |
| Modify | `tests/unit/test_import_boundaries.py` | One-way executable-profile dependency proof |

Conditional path: `uv.lock` must not change. No dependency is added.

No file under `src/dungeonmind/` may change in this PR. If a core runtime or core contract file appears necessary, stop and re-decompose the capability.

## §13 Work plan

1. **Re-anchor and audit** — confirm base commit; inspect open PRs; grep for new D&D or candidate work; record current import-boundary rules; confirm no core file needs modification. Proof: `git rev-parse HEAD`, `git status --short`, `rg -n -i 'threat|candidate|vocabulary|ontology|taxonomy' src tests Docs`.
2. **Add immutable D&D profile revision v2** — create descriptor; calculate canonical digest; preserve v1 unchanged; add both v1 and v2 to example registry. Proof: descriptor validates through existing `SemanticProfileDescriptor`; digest snapshot test; v1 bytes unchanged.
3. **Add vocabulary contract and catalog** — implement strict catalog models; create exact term inventory; pin v2 profile ref; validate domain/range closure; calculate catalog digest. Proof: package catalog loads; all terms unique and namespaced; all predicate kinds resolve; unknown/duplicate/malformed entries fail.
4. **Add candidate contracts** — implement endpoint, node, relationship, packet models; enforce strict shapes; preserve temporary identity distinction; reuse DungeonMind evidence contracts. Proof: JSON Schema snapshot; strict extra-field rejection; closed evidence and endpoint validators.
5. **Add pure loader/renderer/validator** — use `importlib.resources`; no import-time I/O; deterministic prompt and JSON Schema; package-owned errors; no source prose in errors. Proof: same input renders byte-identical prompt/schema; package import leaves resources unread; validation matrix passes.
6. **Add synthetic Threat fixture** — use candidate/existing endpoint mix; include exact relationships; no mechanics; no canon/write fields. Proof: fixture validates unchanged; serialized fixture has no forbidden fields/terms.
7. **Harden import and package boundaries** — update import tests; inspect wheel contents; prove no optional extras load. Proof: `uv build`, wheel inspection.
8. **Atomic documentation sync** — add ADR-0005; update architecture, authority, roadmap, README, contributing, example docs; check all claims against implementation. Proof: docs identify B.2c as candidate-only; docs do not claim graph publication, identity resolution, mechanics, or multi-system support.

## §14 Atomic documentation sync

Documentation is merge-blocking and must land in the same PR.

### §14.1 ADR-0005

Record: `dungeonmind_dnd` may now contain side-effect-free executable contracts and pure validation; dependency remains strictly one-way; D&D profile v1 remains immutable, v2 is created for concrete semantics; the first catalog is deliberately Threat-oriented and narrow; Threat is a contextual `threatens` relationship, not an object kind; NPC, monster, ally/enemy, creature type, encounter role, and mechanics remain unresolved classifications/roles; candidate identity is not graph identity; existing graph references are explicit but unverified until a graph-aware successor; evidence is mandatory and closed; prompt/schema rendering is deterministic and the prompt is never authority; no generic interpretation layer is created; candidate-to-contribution planning is a successor. Rejected alternatives must include: core D&D enums; open property bags; universal candidate schema in the kernel; Threat kind; graph publication; LLM integration; statblock inclusion; editing profile v1.

### §14.2 Architecture

Add a profile-side candidate layer (descriptor, vocabulary catalog, candidate contracts, deterministic candidate validator, prompt/schema renderer — no graph read/write authority). Clarify: this is not the future interpretation layer; the kernel still validates namespace only; the D&D package validates exact D&D terms for candidate production; a graph can contain profile-qualified terms not produced by this candidate package; candidate validation does not make a fact canonical.

### §14.3 Authority

Add: the checked-in D&D vocabulary catalog is authoritative for B.2c candidate terms; the catalog is not authority over existing graph truth; evidence/source artifacts remain authority for claims; candidate packets are proposals; DungeonMindBuddy docs remain consumer evidence; prompts and model output are never semantic authority.

### §14.4 Roadmap

Update:

```text
B.2b  semantic profile boundary + dm_union_graph_v3 ✅
B.2c  DungeonMindDnD Threat vocabulary + candidates ← current
```

Add outcome: `dnd5e-profile-v2` → `threat-v1` catalog → strict provenance-bearing node/relationship candidates → deterministic domain/range validation → deterministic prompt/schema → existing-node reference proof.

Name successors: **B.2d** graph-aware candidate resolution and reviewable contribution planning; **B.3** exact external mechanics/statblock binding for a Threat consumer. Do not renumber external C/D/E/F lanes.

### §14.5 README

State: `dungeonmind_dnd` now contains executable pure candidate contracts; it is still in the same wheel; kernel never imports it; the first vocabulary is intentionally tiny; no graph write, LLM, mechanics, or second system exists.

### §14.6 CONTRIBUTING

Replace "data-only" with exact executable-profile rules. Add: D&D semantic terms belong only under `src/dungeonmind_dnd`; new vocabulary terms require a new immutable catalog revision; changing the profile association requires a new profile revision; Threat must not be introduced as an object kind without a new ADR; candidate schemas must carry closed evidence and temporary IDs; no profile package may access repositories, providers, network, or config on import.

### §14.7 Example semantic-profile docs

Explain: v1 and v2 descriptors coexist; v1 remains valid for namespace-only graphs; v2 is the profile identity pinned by the Threat vocabulary; the registry locates descriptors, not the catalog; the D&D package loads its own catalog; deleting v1 or v2 breaks old consumers and is forbidden.

## §15 Explicitly out of scope

### Kernel and persistence

Do not change: any file under `src/dungeonmind/`; `dm_union_graph_v1`, v2, or v3; semantic-profile descriptor/ref schema; graph revision envelope; repositories; migrations; API routes; readiness; retrieval; projections; graph scoping; identity resolution.

### Candidate pipeline

Do not implement: packet rendering from raw source prose; chunking; source-unit selection; LLM execution; provider adapters; prompt experimentation framework; extraction run persistence; confidence scoring; exact-match identity blocking; merge verification; contribution planning; review UI; graph publication.

### D&D semantics

Do not implement: statblocks; AC, HP, saves, skills, CR; creature types; spell, item, class, ancestry, condition vocabularies; NPC/PC distinctions; ally/enemy disposition; encounter roles; temporal relationship assertions; classification assertions; mechanics resource bindings; rules text.

### Multi-system work

Do not implement: a generic catalog schema in the DungeonMind kernel; cross-profile mappings; ontology alignment; a second production semantic profile; profile composition; campaign extension vocabularies.

## §16 Acceptance gates

### Core gates

```bash
uv sync --locked
uv run ruff check .
uv run pyright
uv run --no-dev python -c "import dungeonmind"
uv run --no-dev python -c "import dungeonmind_dnd"
uv run pytest -m "not integration"
```

No PostgreSQL integration suite is required unless an implementation unexpectedly touches integration paths—which is a stop condition.

### Focused tests

```bash
uv run pytest -q \
  tests/unit/test_dnd_threat_vocabulary.py \
  tests/unit/test_dnd_threat_candidates.py \
  tests/unit/test_dnd_threat_prompt_schema.py \
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
import dungeonmind_dnd
for forbidden in ("fastapi", "psycopg", "sqlalchemy", "openai", "anthropic"):
    assert forbidden not in sys.modules
print("profile import remains lightweight")
PY
```

### Resource and wheel proof

```bash
uv build
uv run python - <<'PY'
from pathlib import Path
from zipfile import ZipFile

wheel_path = sorted(Path("dist").glob("*.whl"))[-1]
with ZipFile(wheel_path) as wheel:
    names = set(wheel.namelist())

required = {
    "dungeonmind_dnd/profiles/dnd5e-v1.json",
    "dungeonmind_dnd/profiles/dnd5e-v2.json",
    "dungeonmind_dnd/vocabularies/threat-v1.json",
}
missing = sorted(required - names)
assert not missing, missing
print("profile descriptors and vocabulary present")
PY
```

Remove local `dist/` before commit unless repository policy tracks it.

### No-core-drift proof

```bash
git diff --name-only 9d9d8cc1b9fefe9c9cc6bfad5e3d0d6932645e0e...HEAD \
  | rg '^src/dungeonmind/' && exit 1 || true

git diff -- uv.lock migrations src/dungeonmind
```

Expected: no changes.

### Vocabulary audit

```bash
rg -n 'dnd5e:threat("|$)' src tests Docs
# Expected: no object-kind declaration; only explicit negative tests/docs if present

rg -n -i '\b(armor class|hit points|challenge rating|legendary action|spell slot)\b' \
  src/dungeonmind_dnd
# Expected: no matches outside explicit forbidden-term tests/docs
```

## §17 Acceptance rubric

### Boundary

- Base is PR #7 merge commit or an explicitly re-anchored descendant.
- No `src/dungeonmind/` file changed.
- Kernel never imports `dungeonmind_dnd`.
- D&D package imports only the narrow allowed kernel contracts/canonical helper.
- Importing either package causes no network, config, file, provider, or database side effect.
- No dependency or lockfile change.

### Profile and vocabulary

- `dnd5e-v1.json` is byte-for-byte unchanged.
- `dnd5e-v2.json` exists and validates.
- Catalog pins exact v2 profile ref and digest.
- Catalog has exactly four object kinds and four predicates.
- All terms are qualified and unique.
- Predicate domain/range references only catalog kinds.
- Catalog digest is stable and tested.
- Profile/catalog files ship in the wheel.

### Candidate contracts

- Contracts are strict and versioned.
- New candidates carry temporary IDs only.
- Existing graph references are explicit and typed.
- Closed evidence ledger is enforced.
- Unknown terms and foreign namespaces fail.
- Domain/range and direction are enforced.
- Open properties/confidence/provider fields fail.
- At least one `threatens` relationship is required.
- Threat is not an object kind.
- Candidate packets cannot publish or mutate.

### Prompt/schema

- JSON Schema is deterministic.
- Prompt fragment is deterministic and generated from catalog data.
- Prompt lists exact terms and direction.
- Prompt contains no campaign prose or rulebook text.
- Prompt is not used as validation authority.

### Fixture

- Synthetic Tripod Null-Calf packet validates.
- It includes an existing North Gate object reference.
- It proves creature→location threat direction.
- It contains no mechanics/statblock fields.
- All nodes/relationships are evidenced.
- No stable IDs are assigned to new candidates.

### Documentation

- ADR-0005 records the executable-profile and Threat decisions.
- Architecture, authority, roadmap, README, contributing, examples, and handoff agree.
- B.2b is marked landed.
- B.2c is described as candidate-only.
- No doc claims graph publication, identity resolution, D&D completeness, ontology interpretation, or multi-system support.

## §18 Stop conditions

Stop and report before implementation or before broadening if any applies:

- main contains overlapping candidate/vocabulary work.
- A core `src/dungeonmind/` change appears necessary.
- Existing semantic-profile contracts cannot carry v2 without modification.
- The catalog requires a generic kernel term registry.
- Candidate validation requires a graph repository read.
- Existing-object references cannot remain explicitly unverified.
- The worker wants to assign stable object IDs.
- The worker wants to merge aliases or identity.
- The worker wants to publish a graph revision or contribution.
- The worker wants to call an LLM.
- The worker wants to add statblock/mechanics fields.
- The term inventory expands beyond the exact four kinds/four predicates.
- A second profile/system is needed to justify an abstraction.
- A new dependency is required.
- Fixtures require licensed rules text or sensitive campaign prose.
- The D&D package needs application/infrastructure/service imports.
- The package requires import-time registration or config discovery.
- Documentation cannot remain truthful without claiming interpretation or publication.

Stop report format:

```text
Stop condition:
Discovered fact:
Affected invariant:
Paths/contracts involved:
Why B.2c cannot absorb it:
Smallest revised capability:
Safe work completed:
Work not attempted:
Operator decision required:
```

## §19 What remains false after merge

Even after successful B.2c:

- DungeonMind does not understand D&D terms.
- The kernel still admits only namespaces, not exact terms.
- No generic interpretation layer exists.
- No raw prose is converted into candidates.
- No LLM is invoked.
- No extraction run is persisted.
- No identity resolution occurs.
- No candidate is canonical.
- No candidate becomes a graph contribution.
- No graph revision is published.
- Existing object references are not verified against a graph.
- No classification/facet assertion system exists.
- Threat has no product projection or lifecycle.
- No statblock or mechanics binding exists.
- No combatant hydration exists.
- No player/GM candidate review exists.
- No product surface adopts the package.
- Only one narrow D&D vocabulary exists.
- No second game system exists.
- No cross-profile ontology/taxonomy layer exists.
- `dungeonmind_dnd` remains in the same distribution.

## §20 Named successors

### B.2d — Graph-aware candidate resolution and contribution planning

Independently useful outcome: validated D&D candidates → graph-aware existing-node verification → exact-match identity blocking → explicit unresolved/merge/new outcomes → non-mutating reviewable contribution plan. Still no automatic publication.

### B.3 — Threat mechanics-resource binding

Independently useful outcome: approved Threat graph identity → exact external statblock/mechanics resource ref → revision/digest pin → profile-owned hydration contract. Mechanics stay outside the graph body.

### Later interpretation layer

Only after a materially different second system creates pressure: profile-specific catalogs and candidate semantics → compare actual commonalities → design a generic interpretation interface from evidence. Do not schedule or design it in B.2c.

## §21 Required PR handback

The PR body must be the merge contract and include:

- **Exact state:** repository, branch, base SHA, head SHA, PR number, status, changed paths, paths outside allowlist.
- **Profile/catalog matrix:** artifact, ID, revision, digest, purpose (D&D profile v1, D&D profile v2, Threat catalog).
- **Vocabulary table:** all eight terms and exact domain/range.
- **Candidate proof:** valid fixture result; JSON Schema digest/snapshot; prompt fragment digest/snapshot; each negative validation case; evidence closure; existing-object endpoint behavior; confirmation that no stable IDs/write fields exist.
- **Boundary proof:** no core changes; import tests; modules loaded after kernel/profile imports; wheel contents; v1 descriptor unchanged.
- **Verification:** exact commands and actual results (sync; Ruff; Pyright; focused tests; full non-integration suite; import proof; wheel proof; no-core-drift proof; CI).
- **Documentation sync:** exact updates to ADR-0005, architecture, authority, roadmap, README, contributing, example registry/docs, checked-in handoff.
- **Remaining false:** copy §19 and remove only statements actually made true.

## §22 Reviewer protocol

Review this as a semantic-discipline and package-boundary PR, not as a feature-completeness PR.

### Reconstruct intent

Before reading code, state: this PR makes D&D candidate production constrained and testable. It does not make candidates canonical, make DungeonMind understand D&D, or implement Threat/statblock product behavior.

### Adversarial review cases

- Import `dungeonmind` → `dungeonmind_dnd` must not load.
- Import `dungeonmind_dnd` → no package-data read, provider, DB, API, or config side effect.
- Modify `dnd5e-v1.json` → review fails immediately.
- Change one catalog term without changing vocabulary revision → digest snapshot fails.
- Submit `dnd5e:threat` as kind → reject.
- Submit `dnd5e:located_at` location→creature → reject.
- Submit `dnd5e:threatens` creature→location → accept.
- Reference `obj:north-gate` without expected kind → reject.
- Reference a missing candidate ID → reject.
- Add properties, confidence, object_id, or graph_revision_id → strict contract rejects.
- Remove one evidence ref from the packet ledger → reject.
- Add an unused evidence ref → reject.
- Remove all `threatens` relationships → reject as wrong packet type.
- Inspect prompt fragment → exact catalog terms/direction only; no rulebook/campaign prose.
- Inspect wheel → v1, v2, and catalog present.
- Inspect diff → no `src/dungeonmind/`, migration, API, DB, graph schema, or retrieval changes.

### Approval bar

Approve only when the reviewer can truthfully say:

> DungeonMindDnD now owns one small, immutable D&D vocabulary and can validate provenance-bearing Threat candidates without graph authority. The kernel remains D&D-blind, Threat remains contextual rather than ontological identity, and every later step—LLM extraction, identity resolution, contribution planning, publication, mechanics, and multi-system interpretation—remains a separate capability.

## §23 Opening directive for the implementation agent

Start from merge commit `9d9d8cc1b9fefe9c9cc6bfad5e3d0d6932645e0e`. Implement exactly B.2c inside `src/dungeonmind_dnd`: preserve the v1 descriptor, add a v2 profile descriptor, add the exact four-kind/four-predicate Threat vocabulary, add strict provenance-bearing node/relationship candidate contracts, add deterministic catalog loading, JSON Schema/prompt rendering, and candidate validation, and prove the contract with a synthetic Tripod Null-Calf packet that connects to an existing North Gate object reference. Update only import-boundary tests, packaging, examples, and atomic architecture/authority/roadmap/ADR/README/contributing/handoff documentation outside the D&D package. Do not change any `src/dungeonmind/` file. Do not call an LLM, read a graph, resolve identity, plan a contribution, publish a revision, model mechanics/statblocks, add a generic interpretation layer, or add another game system.
