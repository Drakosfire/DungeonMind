# HANDOFF — V1.2: legacy v1–v6 compatibility decoder + semantic parity

**Created:** 2026-09-15  
**Status:** ACTIVE  
**Repository:** `Drakosfire/DungeonMind`  
**Suggested implementation branch:** `kernel/v1-2-legacy-compatibility-parity`  
**Design / implementation base:** DungeonMind `main` at `6d9a40f609530f4882470c5599b4914e2288b8d5` — merged PR #57  
**Predecessor:** PR #57 — `KERNEL: immutable ParsedKnowledgeRevision core and structural indexes`  
**Accepted V1.1 implementation head:** `38d9eac3252ba911ff7565b930ce8b84aca0767b`  
**V1.1 final disposition:** `V1_1_PARSED_KNOWLEDGE_REVISION_CORE_ACCEPTED`  
**V1.1 final review:** `5213422370` — 2 logical review cycles  
**Canonical V0 contract aggregate:** `fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`  
**Roadmap phase:** V1 — immutable normalized revision + revision-local indexes  
**Slice:** V1.2 — frozen historical compatibility + parity  
**Successor if accepted:** V2 — generic `KnowledgeReadContext` + candidate admission seam  
**One-line mission:** verify each immutable historical `dm_union_graph_v1` through `dm_union_graph_v6` stored revision, decode it through the frozen historical semantics, and normalize it into the accepted V1.1 immutable serving model with deterministic semantic parity — without rewriting history, performing admission, or pretending legacy payloads are native vNext authority.

---

## §0 Mandatory first commit — update the living Steward handoff

**This is part of the PR's acceptance contract, not optional documentation cleanup.**

PR #57 has merged, so the stewardship mutation protocol requires the successor branch to record that merge before another roadmap PR is allowed to merge.

The **first commit on the V1.2 implementation branch** must update:

```text
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
```

Do this before implementation commits.

The Steward update must record at minimum:

```text
current DungeonMind main / merge anchor:
  6d9a40f609530f4882470c5599b4914e2288b8d5

last merged roadmap PR:
  PR #57 — KERNEL: immutable ParsedKnowledgeRevision core and structural indexes

accepted implementation head:
  38d9eac3252ba911ff7565b930ce8b84aca0767b

final disposition:
  V1_1_PARSED_KNOWLEDGE_REVISION_CORE_ACCEPTED

logical review cycles:
  2

final PASS review:
  5213422370

V1.1 benchmark:
  Docs/Benchmarks/vnext_parsed_knowledge_revision_10k_v1.json
  assertions: 10,000
  entities: 5,000
  evidence refs: 2,500
  aliases: 2,000
  build: ~7004.647 ms
  peak traced memory: ~48.53 MiB
  semantic digest:
    8b51a341d7464710be1410421a843d31fa2e84e9387d0043e131575d44d2379d
  compatibility key:
    b795c672dbf87394b83ebaba42976b54994b257ed5beefa93b7cc184f82bc9e5
  indexed lookups: microsecond-scale characterization

roadmap state:
  V0 COMPLETE — VNEXT_CONTRACT_FROZEN
  V1 ACTIVE
  V1.1 COMPLETE
  V1.2 ACTIVE

what remains false:
  v1-v6 -> ParsedKnowledgeRevision compatibility parity is not yet proven
  overall V1 is not complete
  V2 is not yet active
  current public World readers still use the historical path
  no bridge-genesis migration has occurred
  no vNext cutover has occurred

next primary question:
  the V1.2 question in §1 of this handoff
```

Also update the Steward's safe/blocked parallel-work notes:

```text
safe / independent:
  larger-scale benchmark characterization
  already-contract-frozen Buddy/domain work that does not depend on V2 runtime

still blocked by V1 completion:
  V2 merge
  V3+ Kernel read-path rollout
  bridge-genesis migration
  cutover
  deletion/quarantine of current public historical readers
```

Do not turn the Steward file into a diary. Replace its stale V1.1 checkpoint with the current V1.2 checkpoint.

**PR review gate:** if the V1.2 branch history does not contain this Steward bookkeeping as the first successor commit, return the PR for bookkeeping repair before merge.

**After V1.2 eventually merges:** the V2 successor branch must again update the Steward handoff as its first bookkeeping change, recording the actual V1.2 merge SHA, accepted head, review-cycle count, parity artifact identity, V1 completion, and V2 as active before V2 is allowed to merge.

---

## §1 Primary question and exit

Answer one question:

> **Can every frozen historical `dm_union_graph_v1` through `dm_union_graph_v6` stored revision be verified and decoded into the accepted immutable `ParsedKnowledgeRevision` with deterministic semantic parity to the current historical reader, without rewriting history, performing admission, or pretending legacy payloads are native vNext authority?**

The target serving shape is:

```text
StoredGraphRevision
  exact immutable legacy envelope
  + exact legacy payload
        ↓
verify legacy envelope / canonical payload digest
        ↓
VersionedUnionGraphSnapshotReader
  frozen v1-v6 semantic oracle
        ↓
legacy compatibility normalization
        ↓
ParsedKnowledgeRevision
  immutable records
  + deterministic revision-local indexes
```

Successful slice disposition:

```text
V1_2_LEGACY_COMPATIBILITY_PARITY_ACCEPTED
V1_IMMUTABLE_NORMALIZATION_COMPLETE
```

Only after both are true may V2 become the active Kernel roadmap phase.

---

## §2 Authority and required reading

Before coding, re-read current checked-in versions in this order:

1. `Docs/Architecture/AUTHORITY.md`
2. `Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`
   - especially old-history preservation / compatibility posture;
3. `Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md`
   - especially `ParsedKnowledgeRevision`, compatibility identity, and derived-index rules;
4. `Docs/Roadmaps/ROADMAP.md` — V1 proof and stop conditions;
5. `Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md` — after completing §0;
6. `Docs/Handoffs/HANDOFF-v1-1-parsed-knowledge-revision-core.md`;
7. `src/dungeonmind/application/vnext/` — accepted V1.1 model/builder/index implementation;
8. historical revision + reader authority:

   ```text
   src/dungeonmind/contracts/graph.py
   src/dungeonmind/application/graph_snapshot.py
   src/dungeonmind/application/graph_snapshot_v4.py
   src/dungeonmind/application/graph_snapshot_v5.py
   src/dungeonmind/application/graph_snapshot_v6.py
   src/dungeonmind/contracts/knowledge_assertion.py
   src/dungeonmind/application/graph_scope.py
   ```

9. existing historical schema-lock and reader tests.

Repository truth outranks this handoff. If current accepted architecture contradicts a detail here, STOP and rebrief rather than silently choosing this document.

---

## §3 Binding compatibility posture

### 3.1 This is a codec, not a migration

Historical v1-v6 revisions remain immutable authority records.

V1.2 must not:

```text
rewrite an old payload
republish an old revision as vNext
mint a bridge-genesis revision
advance a head
persist a synthetic KnowledgeRevision
replace a historical revision's graph_schema
claim a legacy payload was always native vNext
```

The vNext architecture is explicit:

> old revisions remain readable through historical compatibility; they are not transformed in place.

`ParsedKnowledgeRevision` is a derived serving representation. For a legacy revision it is a **compatibility-normalized view**, not new durable truth.

### 3.2 The frozen historical readers are the semantic oracle

`VersionedUnionGraphSnapshotReader` and its v1-v6 readers define the currently accepted interpretation of immutable historical graph bytes.

V1.2 may call or compose those readers. It must not opportunistically “fix,” simplify, or reinterpret them.

If parity seems to require changing a historical reader, STOP and determine whether:

```text
A. the compatibility mapping is wrong; or
B. a genuine historical-reader defect has been discovered.
```

Do not repair B inside this PR without an explicit rebrief.

### 3.3 Normalize stored knowledge, not an admitted projection

The compatibility decoder operates before current request-specific:

```text
campaign scope
GM / PLAYER admissibility
source lifecycle authority
provenance admission
domain admission
focus/ranking
```

It must preserve the information later admission needs; it must not decide what a request may see.

Source/provenance freshness remains a V2 read-context concern.

---

## §4 Write lease

### In scope

1. Add one quarantinable application-layer historical compatibility seam, preferred shape:

   ```text
   src/dungeonmind/application/vnext/legacy_compat.py
   ```

   or:

   ```text
   src/dungeonmind/application/vnext/compat/legacy_world.py
   ```

2. Accept an exact `StoredGraphRevision` or equivalent exact immutable legacy envelope + payload.
3. Verify envelope/payload identity before compatibility normalization.
4. Dispatch only `dm_union_graph_v1` through `dm_union_graph_v6` through the existing historical reader.
5. Translate the parsed historical meaning into V1.1 immutable records/indexes.
6. Add a deterministic internal compatibility mapping identity/version.
7. Add semantic parity witnesses/artifacts for all six historical graph schemas.
8. Add malformed-history fail-closed witnesses.
9. Add one relevant 10k legacy-v6 compatibility characterization if practical without distorting this slice.
10. Extend import/boundary tests so the compatibility seam remains quarantinable and does not pull product/D&D semantics into generic vNext code.

### Out of scope — falsification

This PR must **not**:

- switch current production World reads to `ParsedKnowledgeRevision`;
- modify public retrieval DTOs;
- add `KnowledgeReadContext`;
- perform scope, visibility, standing, provenance, or domain admission;
- query source repositories for current lifecycle/authority state;
- add PostgreSQL schema/repositories/migrations;
- change publication/materialization/write behavior;
- create bridge genesis;
- repin DungeonMindBuddy;
- modify the frozen V0 wire contracts or aggregate;
- introduce a new public compatibility wire protocol;
- rewrite any v1-v6 durable payload;
- delete or quarantine the historical readers yet;
- add Redis/global caches/vector search;
- claim V2/V3 performance targets;
- import `dungeonmind_dnd` into generic Kernel/compatibility code.

---

## §5 Exact stored-revision verification

Compatibility starts from exact authority bytes, not a caller-trusted object graph.

Before semantic normalization, verify at minimum:

1. the envelope uses the existing historical `WorldGraphRevision` contract;
2. `revision.world_id` exactly matches payload `world_id`;
3. `revision.graph_schema` is exactly one of:

   ```text
   dm_union_graph_v1
   dm_union_graph_v2
   dm_union_graph_v3
   dm_union_graph_v4
   dm_union_graph_v5
   dm_union_graph_v6
   ```

4. the payload canonical digest recomputes with the historical canonicalization rules to exactly `revision.graph_payload_sha256`;
5. the historical reader accepts the payload under that exact schema;
6. semantic-profile verification required by v3-v6 uses the existing pinned registry rules.

Digest mismatch, world mismatch, unsupported schema, malformed profile state, dangling references, duplicate IDs, and other corrupt historical state fail closed through the existing integrity error family or a compatibility-specific integrity error that subclasses it.

Do not normalize malformed bytes and then hope later admission rejects them.

---

## §6 Internal compatibility identity

Legacy normalization needs an identity that is safe for parsed-state reuse but does not pretend the old revision is a native vNext `KnowledgeRevision`.

Define a fixed internal compatibility format/version, for example:

```text
dm_legacy_world_compat_v1
```

The exact name may differ. The properties may not.

Compatibility identity must cover every input that can change normalized meaning, including at minimum:

```text
compatibility decoder / mapping revision
legacy graph_schema
historical reader parse compatibility identity
legacy semantic-profile identity where present
V1.1 parsed format revision
exact legacy graph payload digest
```

If a mapping rule changes, parsed compatibility identity must change.

A small deterministic checked-in manifest is encouraged, for example:

```text
Docs/Compatibility/dm_legacy_world_compat_v1.json
```

If used, it should contain only mapping identity/rules needed to make normalization auditable and digest-pinned. It is **not** a new public wire contract.

### Parsed domain/profile refs

V1.1 `ParsedKnowledgeRevisionIdentity` requires internal domain/profile identity. Legacy history did not have vNext refs.

Use deterministic compatibility-only identities. They must be visibly non-native and non-durable.

For v3-v6, include the exact historical `SemanticProfileRef` in the compatibility identity/digest. Do not silently treat a legacy profile descriptor as a native `SemanticProfileDescriptorV2` if it is not one.

For v1-v2, use an explicit deterministic **legacy-unprofiled** compatibility identity; do not fabricate a historical semantic profile that never existed.

Do not create or persist a public `KnowledgeRevision` merely to satisfy the V1.1 builder API. A small internal refactor that lets the accepted V1.1 builder consume an internal parsed identity/normalized record set is allowed if:

- V1.1 behavior/digests stay stable for native vNext inputs;
- V1.1 focused tests remain exact;
- no public V0 contract changes;
- the distinction between native-vNext and legacy-compatibility parsing remains explicit.

---

## §7 Semantic mapping rules

The decoder must preserve meaning, not merely make types validate.

### 7.1 Stable identity

```text
legacy world_id  → parsed space_id value, byte-for-byte/string-for-string
legacy object_id → parsed entity_id value exactly
legacy revision_id / parent / created_at / operation_ids / payload digest
                  → exact parsed identity fields
```

Do not re-ID because field names changed.

### 7.2 Entity presence is not legacy assertion admission

An `Entity` is an identity anchor in vNext.

For v4-v6, object existence itself is a scoped/visible assertion with exact metadata. Preserve that existence assertion separately.

Do not infer:

```text
entity exists in ParsedKnowledgeRevision
therefore every caller may observe the object
```

Later admission owns that question.

### 7.3 Historical object fields

Preserve the historical reader's meaning for:

```text
kind
label
aliases
summary
properties
```

Encode them through deterministic compatibility assertions / internal normalized records without teaching generic Kernel code that a label, NPC, location, or World is special.

Where a historical field has no durable assertion ID, synthesize one deterministically from stable legacy identity + field role + compatibility format. Never use random IDs or payload array position alone when order is not semantic identity.

Synthetic-ID formulas must be documented and collision-tested.

### 7.4 Relationships

Every legacy relationship becomes an entity-valued normalized assertion.

Preserve exactly:

```text
source/subject entity ID
target/object entity ID
predicate
legacy relationship identity
assertion metadata/evidence where present
```

For v4-v6, prefer the exact stored assertion identity from relationship assertion metadata as the normalized assertion identity when that is the authoritative claim ID.

If `relationship_id` differs from assertion identity, preserve `relationship_id` in compatibility metadata so the old semantic witness can be reconstructed losslessly.

For v1-v3, derive a deterministic normalized assertion ID from the exact legacy relationship identity and compatibility mapping version.

### 7.5 v6 endpoint aspects

V6 endpoint aspect assertions are semantically significant. A relationship may name one exact admitted aspect assertion per endpoint.

Do not drop:

```text
source_aspect_assertion_id
target_aspect_assertion_id
```

Preserve enough compatibility metadata to reconstruct `effective_endpoint_kind()` exactly from the normalized compatibility view.

If endpoint-aspect semantics cannot be represented losslessly without changing the frozen public vNext contract, STOP rather than flattening them.

### 7.6 Duplicate/conflicting assertions

Do not collapse:

```text
multiple properties with one predicate
conflicting property values
multiple aliases with same text
distinct assertion IDs carrying similar content
```

The historical readers intentionally preserve these conflicts. Compatibility must too.

### 7.7 Aliases — mandatory design checkpoint

This is a known risk and must be addressed explicitly in the PR description and tests.

Current v4-v6 alias assertions can carry their own:

```text
campaign scope
visibility
epistemic/canon state
evidence
session refs
temporal scope
```

Native vNext `IdentityAlias` does **not** carry all those axes.

Therefore:

> **Do not blindly translate every historical alias assertion into native `IdentityAlias`.**

Doing so could turn a hidden/scoped historical alias into a pre-admission identity candidate and leak the alias→entity association.

Acceptable approaches include preserving scoped historical aliases as ordinary compatibility assertions with their complete metadata, while using `IdentityAlias` only for legacy alias material proven semantically equivalent to Kernel identity aliasing.

Required proof:

- a GM-only/scoped alias does not become an unconditional alias-index candidate merely because compatibility normalization occurred;
- ambiguity is preserved;
- the normalized semantic witness can reconstruct the historical alias assertions exactly.

If the V1.1 model cannot preserve this without weakening visibility semantics, STOP and return a design report.

### 7.8 v4+ assertion metadata

Preserve each field deliberately.

#### campaign scope

Translate legacy `campaign_scope` into a compatibility-qualified generic scope binding.

The compatibility module may understand that historical field because it is explicitly a **legacy World compatibility codec**. Generic vNext code outside this seam must not gain a `campaign_id` dependency.

`None` remains world-universal/unscoped.

#### visibility

Translate legacy GM/PLAYER visibility to compatibility-qualified audience labels without performing admission.

Do not use visibility to remove assertions in V1.2.

Do not make generic Kernel code branch on `GM` or `PLAYER`; the translation stays quarantined inside compatibility.

#### epistemic kind

`KnowledgeAssertionMetadataV1` explicitly says:

```text
fact is not an alias for asserted
source_derived_candidate is not an alias for inferred
```

Preserve that distinction.

For values with an exact native epistemic-basis equivalent (`asserted`, `inferred`, `speculative`), exact mapping is allowed.

For legacy-only values, do not silently coerce them into a native enum meaning. Because legacy compatibility is not native vNext, the internal normalized representation may retain a compatibility-only value and/or domain metadata as needed, provided:

- the original value is losslessly reconstructible;
- native vNext wire serialization is not claimed;
- later V2 can distinguish the compatibility semantics;
- the mapping is version/digest-bound.

If those conditions cannot be satisfied with V1.1 without semantic lying, STOP.

#### canon / standing

Map to generic standing only where the equivalence is explicit and lossless.

Preserve the original legacy canon value in compatibility metadata whenever needed for exact parity.

Do not collapse rejected/unresolved contribution state into graph standing; V1.2 reads published graph history only.

#### evidence

Evidence ref IDs are exact identity and must be preserved.

#### session refs

Historical `session_refs` mean real-world sessions in which an assertion surfaced.

They are **not**:

```text
scope
authorization
fictional time
```

Preserve them as compatibility/domain metadata or equivalent exact context. Never infer scope or chronology from them.

#### temporal scope

Preserve the explicit distinction:

```text
legacy unknown          → unknown
legacy world_timeless   → timeless
legacy fictional_time_ref
                        → compatibility domain_ref preserving exact
                           bundle_id + campaign_id + anchor_id
```

Never convert unknown to timeless.
Never derive fictional time from session refs.

### 7.9 v1-v3 coarse semantics — mandatory design checkpoint

V1-v3 do not carry v4 assertion-scoped campaign/visibility/temporal metadata.

Do not fabricate modern stored facts that were not present.

The compatibility mapping must preserve the historical semantics that actually existed:

```text
coarse object fields
coarse relationship fields
coarse evidence support
historical semantic-profile identity where present
source-derived admission deferred to the read context
```

A neutral assertion-level requirement may be used only if it is proven not to broaden or narrow the current reader once V2 provenance admission is applied. Document the rationale explicitly.

In particular, do not casually assert that v1-v3 content was historically:

```text
PLAYER-visible
GM-only
campaign-global
world-timeless
asserted
```

unless checked-in historical semantics actually prove that meaning.

For historical concepts with no native vNext equivalent, preserve an explicit compatibility value/metadata instead of guessing.

If required V1.1 fields force a permissive semantic guess, STOP and rebrief.

### 7.10 Evidence records

Preserve exact historical evidence identity and reconstructible locator/support data.

Native generic evidence roles that are already exact (`support`, `contradiction`, `context`) may map directly.

Historical source-domain/classification values may be preserved as compatibility/domain metadata. Do not resurrect the World `SourceDomain` enum as a generic vNext Kernel concept.

V1.2 does **not** read current source artifact lifecycle/visibility and does not decide whether the evidence currently admits the assertion.

---

## §8 Semantic parity witness

Raw old DTOs and the new normalized model have different shapes. Do not compare them by accidental JSON shape.

Define one deterministic **legacy semantic witness** that captures the authority-relevant meaning common to both representations.

Preferred conceptual path:

```text
historical reader output
→ canonical semantic witness A

compatibility-normalized ParsedKnowledgeRevision
→ canonical semantic witness B

canonical_json(A) == canonical_json(B)
sha256(A) == sha256(B)
```

The witness must capture, where present in that schema generation:

```text
world/space identity
object/entity IDs
kind
label
alias assertions + IDs + metadata
summary assertion + metadata
property assertions + IDs + values + metadata
relationship identity
relationship endpoints + predicate
relationship assertion metadata
v6 endpoint aspect identity and effective endpoint semantics
evidence refs / artifact/revision/locator identity
semantic-profile identity
v4+ campaign scope
v4+ visibility
v4+ epistemic kind
v4+ canon standing
v4+ session refs
v4+ temporal state
```

Do not compare only counts.

### Required machine-readable parity artifact

Add a deterministic artifact, suggested path:

```text
Docs/Compatibility/legacy_v1_v6_parity_v1.json
```

For each v1-v6 witness record at minimum:

```text
graph_schema
fixture / workload identity
legacy payload sha256
historical-reader semantic witness sha256
compat-normalized semantic witness sha256
ParsedKnowledgeRevision semantic_digest
ParsedKnowledgeRevision compatibility_key
entity count
normalized assertion count
entity-ref/relationship assertion count
evidence count
alias assertion / identity-alias count as applicable
parity = PASS
```

Also record:

```text
compatibility mapping revision
mapping/manifest sha256
accepted V1.1 parsed format revision
```

Artifact generation/check must be deterministic. Checked-in digests must be literal expected values, not self-comparisons.

---

## §9 Fixture / witness coverage

Use existing historical test builders/fixtures where possible rather than inventing a second interpretation of each old schema.

At minimum provide one deterministic stored-revision parity witness for every graph schema:

### v1

Exercise:
- coarse node identity/kind/label/aliases/summary;
- relationship;
- evidence;
- no semantic profile.

### v2

Exercise:
- core object evidence;
- alias assertion IDs/evidence;
- summary assertion ID/evidence;
- relationship;
- no semantic profile.

### v3

Exercise:
- exact pinned historical semantic profile;
- qualified kinds/predicates;
- v2-shaped alias/summary semantics.

### v4

Exercise:
- existence assertion;
- independently scoped alias;
- summary;
- duplicate/conflicting property assertions;
- relationship assertion;
- GM/PLAYER distinction;
- campaign scope;
- session refs;
- unknown vs world-timeless;
- fictional-time ref.

### v5

Exercise:
- v4 assertion semantics;
- lossless newer evidence/provenance record shape.

### v6

Exercise:
- object aspect assertions;
- relationship source/target endpoint aspect references;
- effective endpoint kind reconstruction;
- all v5 authority metadata remains intact.

### Malformed / adversarial witnesses

At minimum prove fail-closed behavior for:

```text
payload digest mismatch
world_id envelope/payload mismatch
unsupported graph_schema
missing required semantic profile
profile digest/registry mismatch
duplicate object/entity identity
duplicate assertion identity
duplicate relationship identity
dangling relationship endpoint
dangling evidence ref
invalid v6 endpoint aspect reference
malformed JSON-compatible assertion value where historical schema forbids it
```

The compatibility path need not reproduce the exact historical exception message, but it must remain in the integrity-error family and must not produce a partial parsed revision.

---

## §10 Determinism and immutability

For one exact immutable historical revision:

```text
same envelope
same payload bytes/semantic JSON
same historical reader compatibility identity
same mapping revision
```

must yield:

```text
same ParsedKnowledgeRevision semantic digest
same compatibility key
same index memberships/order
same semantic parity witness digest
```

The V1.1 deep-immutability guarantee remains binding. Compatibility normalization may not retain mutable historical Pydantic objects or caller-owned JSON containers inside the parsed result.

Mutation of:

```text
input StoredGraphRevision payload after normalization
historical ParsedGraphSnapshot after translation
caller-owned nested property JSON
```

must not poison the already-built parsed revision.

---

## §11 Performance characterization

V1.2 is not a performance-optimization PR, but the compatibility stage is new O(N) work and should be characterized.

If practical, add one deterministic 10k v6-like compatibility lane measuring:

```text
payload digest verification
historical v6 parse
compatibility translation
V1.1 parsed/index build
end-to-end compatibility normalization
peak traced memory
semantic parity digest before timing interpretation
```

Record the artifact under `Docs/Benchmarks/` with exact workload identity.

There is **no V1.2 latency target**.

Do not claim V3 bounded-read targets from this work. The point is to know the cost of the historical compatibility path and keep it visible while V2/V3 remove it from native-vNext hot reads.

If a 10k compatibility run is impractical in this slice, return exact evidence why and at minimum characterize a smaller deterministic workload. Do not fabricate scale claims.

---

## §12 Boundary guards

Add or extend tests proving:

1. no generic vNext module imports `dungeonmind_dnd`;
2. compatibility code performs no repository/database/network/source-lifecycle access;
3. current public World read/write services are unchanged;
4. historical reader implementation files are unchanged unless the PR hit a stop condition and was explicitly rebriefed;
5. frozen V0 bundle still recomputes exactly to:

   ```text
   fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea
   ```

6. V1.1 native-vNext semantic digests/compatibility behavior remain stable.

A useful diff guard is to explicitly demonstrate no behavioral changes under:

```text
src/dungeonmind/application/graph_snapshot.py
src/dungeonmind/application/graph_snapshot_v4.py
src/dungeonmind/application/graph_snapshot_v5.py
src/dungeonmind/application/graph_snapshot_v6.py
src/dungeonmind/application/graph_scope.py
```

unless a stop/rebrief was triggered.

---

## §13 Focused acceptance matrix

The focused V1.2 suite must prove at least:

1. Steward handoff records PR #57 merge `6d9a40f...` and V1.2 as active;
2. v1 stored revision decodes;
3. v2 stored revision decodes;
4. v3 stored revision decodes with exact historical profile verification;
5. v4 stored revision decodes;
6. v5 stored revision decodes;
7. v6 stored revision decodes;
8. unsupported graph schema fails closed;
9. payload digest mismatch fails closed;
10. world envelope/payload mismatch fails closed;
11. malformed profile state fails closed;
12. malformed historical structural state fails closed;
13. exact `world_id` value becomes exact parsed `space_id` value;
14. exact revision ID / parent / created-at / operation-ID sequence / payload digest are preserved;
15. v3-v6 historical semantic-profile identity participates in compatibility identity;
16. v1-v2 unprofiled compatibility identity is deterministic and explicit;
17. mapping-manifest/version change changes compatibility identity;
18. object IDs become entity IDs without re-ID;
19. v4-v6 existence assertions remain distinct from entity identity;
20. kind/label/summary semantics are parity-complete;
21. duplicate/conflicting properties are not collapsed;
22. relationships preserve source/target/predicate and legacy identity;
23. v4-v6 relationship assertion identity/metadata are preserved;
24. v1-v3 synthetic assertion IDs are deterministic and collision-tested;
25. evidence identities and locator/support metadata are parity-complete;
26. scoped/hidden alias assertions do not become unconditional identity candidates;
27. alias ambiguity remains representable;
28. legacy campaign scope is preserved but not applied;
29. legacy GM/PLAYER visibility is preserved but not applied;
30. `fact` is not silently aliased to `asserted`;
31. `source_derived_candidate` is not silently aliased to `inferred`;
32. legacy canon state is losslessly reconstructible;
33. session refs are preserved but do not become scope;
34. session refs do not become fictional time;
35. unknown temporal state remains distinct from timeless;
36. fictional-time ref preserves exact bundle/campaign/anchor identity;
37. v6 source/target endpoint aspects are losslessly reconstructible;
38. historical-reader witness digest == compatibility witness digest for all six schemas;
39. compatibility output remains deeply immutable under mutation attacks;
40. no source/provenance admission or repository calls occur;
41. V1.1 native-vNext tests remain exact;
42. V0 aggregate remains exact;
43. deterministic parity artifact regenerates byte-for-byte;
44. relevant compatibility benchmark/characterization artifact is recorded or an explicit evidence-backed deferral is returned.

More tests are welcome. Do not reduce this to a counts-only matrix.

---

## §14 Required gates

Return exact output/status for:

```bash
uv sync

uv run pytest -q tests/unit/test_vnext_legacy_compatibility.py
uv run pytest -q tests/unit/test_vnext_parsed_knowledge_revision.py
uv run pytest -q tests/unit/test_graph_snapshot_reader.py
uv run pytest -q tests/unit/test_union_graph_v4.py
uv run pytest -q tests/unit/test_union_graph_v5.py
uv run pytest -q tests/unit/test_graph_snapshot_v6.py
uv run pytest -q tests/unit/test_graph_scope_v6.py
uv run pytest -q tests/unit/test_historical_evidence_schema_locks.py
uv run pytest -q tests/unit/test_import_boundaries.py

uv run pytest -q
uv run pytest -m conformance

uv run ruff check .
uv run pyright

uv run python scripts/generate_vnext_contract_bundle.py --check

git diff --check
```

Use the actual focused test/artifact-generator path if naming differs.

Run current repository CI and report truth exactly.

The repository still has the inherited `benchmark-smoke` failure in `benchmarks/world_graph_reads.py` caused by the missing `reviewed_world_initializations` constructor argument as of the V1.1 merge. If the same exact failure remains and V1.2 does not touch that path, classify it explicitly as inherited baseline debt. If the failure changes, investigate rather than assuming inheritance.

No new PostgreSQL behavior is expected, but existing integration CI must not regress.

---

## §15 Stop conditions

STOP and return a design report instead of coding around any of these:

1. exact historical parity requires changing a frozen V0 public vNext contract;
2. exact historical parity requires rewriting or republishing a v1-v6 revision;
3. a scoped/visible historical alias cannot be represented without becoming an unconditional identity candidate;
4. v1-v3 missing assertion metadata forces a guessed permissive scope/visibility/temporal meaning;
5. `fact` / `source_derived_candidate` or another legacy semantic value must be silently redefined as a different vNext meaning;
6. v6 endpoint aspect semantics cannot be reconstructed losslessly;
7. compatibility requires current source lifecycle/provenance reads during normalization;
8. compatibility requires request scope/audience admission during normalization;
9. the historical reader must be behaviorally modified just to make translation convenient;
10. synthetic normalized IDs cannot be deterministic and collision-safe;
11. compatibility mapping semantics can change without changing compatibility identity;
12. a compatibility index becomes the only copy of authority-relevant information;
13. a 10k characterization can pass only by skipping digest verification, structural validation, or parity proof;
14. V1.1 native-vNext behavior/digests must change to accommodate legacy compatibility;
15. a fake/persisted native `KnowledgeRevision` becomes necessary to represent old history.

Required stop report:

```text
Stop condition:
Exact legacy schema/revision affected:
Historical reader result:
Expected normalized meaning:
Observed representational conflict:
Why a local workaround would change authority semantics:
Options considered:
Recommended architecture/roadmap change:
Impact on V1 completion / V2 / migration:
```

A stop report is a valid V1.2 result if the current architecture is genuinely insufficient. Do not weaken historical correctness merely to finish V1.

---

## §16 Handback requirements

Return all of the following for review:

1. exact PR base SHA;
2. exact PR head SHA;
3. commit list / nano-commit story;
4. confirmation that the **first successor commit updated the Steward handoff** with PR #57 merge truth;
5. changed-file list;
6. compatibility module/API summary;
7. exact compatibility mapping revision and manifest/artifact digest;
8. one mapping table showing how each v1-v6 semantic family is represented;
9. explicit alias-risk resolution;
10. explicit v1-v3 coarse-semantics resolution;
11. explicit `fact` / `source_derived_candidate` resolution;
12. explicit v6 endpoint-aspect resolution;
13. parity artifact path and all six parity digests;
14. malformed-history/fail-closed matrix;
15. V1.1 regression results;
16. V0 aggregate check result;
17. benchmark/characterization result, if run;
18. Ruff / Pyright / unit / conformance / integration CI results;
19. inherited failures named exactly;
20. `git diff --check` result;
21. explicit list of historical reader/public production files confirmed unchanged;
22. what remains false after this PR;
23. recommended successor if accepted.

The PR description is the merge contract. It should use these headings:

```text
Primary question
Base / identity
Steward bookkeeping
Changed surface
Compatibility mapping
Semantic parity evidence
Fail-closed evidence
Performance characterization
Regression / CI evidence
Known inherited failures
What remains false
Successor
```

---

## §17 What remains false even after a successful V1.2

A successful V1.2 completes **V1**, not the roadmap.

It does not prove:

```text
KnowledgeReadContext
fresh targeted provenance per read
candidate-local generic admission
native vNext exact entity retrieval
complete entity retrieval on vNext
bounded neighborhoods/search/evidence/anchors
vNext governed writes
Buddy runtime domain implementation
bridge-genesis migration
joint V8 acceptance
cutover
historical-reader quarantine/removal
```

After V1.2 merges and the successor Steward mutation is durable, the next Kernel question becomes V2:

> **Can one exact parsed revision support coherent generic + domain admission over bounded candidates without pre-projecting the entire KnowledgeSpace, while keeping source/provenance authority fresh?**

Do not start V3 merely because V1 normalization is fast or complete.

---

## §18 Review disposition vocabulary

Use these exact slice dispositions:

```text
V1_2_HOLD
V1_2_REBRIEF_REQUIRED
V1_2_LEGACY_COMPATIBILITY_PARITY_ACCEPTED
```

Only the final accepted state may additionally declare:

```text
V1_IMMUTABLE_NORMALIZATION_COMPLETE
```

If the reviewed PR head moves after acceptance, re-review the new exact head before merge.
