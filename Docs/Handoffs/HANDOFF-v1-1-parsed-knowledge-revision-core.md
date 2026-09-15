# HANDOFF — V1.1: immutable ParsedKnowledgeRevision core + deterministic indexes

**Created:** 2026-09-15
**Status:** ACTIVE
**Repository / branch:** `Drakosfire/DungeonMind` / suggested implementation branch `kernel/v1-1-parsed-knowledge-revision`
**Design anchor:** DungeonMind `main` at `71b7c857a3eb3fe39e0ee3bb118eb34284a95501`
**Predecessor:** DungeonMindBuddy PR #719 — V0.2 consumer/domain proof; merged at `c77056b0c909513cecd8b81f9e7fac22e02d339a` (substantive PASS head `2a17226b6b0b25a1084f404b6aca8bde442e4713`, disposition `V0_2_DUNGEONBUDDY_DOMAIN_PROOF_ACCEPTED`)
**Canonical V0.1 contract aggregate:** `fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`
**Roadmap phase:** V1 — immutable normalized revision + revision-local indexes
**Slice:** V1.1 — normalized immutable core only
**Successor:** V1.2 — legacy v1-v6 compatibility decoder into the accepted V1.1 model + semantic parity proof
**One-line mission:** establish one domain-agnostic, genuinely immutable internal revision representation and deterministic structural indexes over already-decoded vNext knowledge primitives, without changing storage, admission, public reads, historical readers, or the frozen V0 contract.

---

## Activation gate

**Activated:** 2026-09-15

All activation conditions are satisfied:

1. DungeonMindBuddy PR #719 received final disposition:

   ```text
   V0_2_DUNGEONBUDDY_DOMAIN_PROOF_ACCEPTED
   ```

2. PR #719 was merged into Buddy `main` at `c77056b0c909513cecd8b81f9e7fac22e02d339a` (head `2a17226b6b0b25a1084f404b6aca8bde442e4713`).
3. The DungeonMind living Steward handoff (`Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md`) is updated to record:
   - Buddy PR #719 merge anchor (`c77056b0c909513cecd8b81f9e7fac22e02d339a`);
   - Buddy substantive/reviewed head (`2a17226b6b0b25a1084f404b6aca8bde442e4713`);
   - V0.2 acceptance artifact identity (`Docs/Contracts/vnext/dmb_v0_2_contract_acceptance_v1.json`);
   - `VNEXT_CONTRACT_FROZEN`;
   - V1.1 as the active next Kernel slice.
4. The implementation branch `kernel/v1-1-parsed-knowledge-revision` is created from the activated DungeonMind `main`.
5. The V0 contract artifact still recomputes exactly to:

   ```text
   fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea
   ```

---

## §1 Outcome

Answer one primary question:

> **Can already-decoded vNext knowledge primitives be normalized once into one immutable, deterministic, revision-local internal model whose structural indexes are rebuildable and semantically lossless, without performing scope/visibility/domain admission or introducing World/TTRPG meaning into the Kernel?**

The accepted end state is an internal application-layer model named `ParsedKnowledgeRevision` (or an equally clear name) with this conceptual shape:

```text
exact KnowledgeRevision identity
+ exact pinned DomainContractRef
+ exact pinned SemanticProfileRef
+ immutable entities/assertions/aliases/evidence
+ deterministic revision-local structural indexes
```

This slice is intentionally narrower than the complete roadmap V1 exit.

It proves the normalized target model before asking six historical graph generations to map into it.

Successful slice disposition:

```text
V1_1_PARSED_KNOWLEDGE_REVISION_CORE_ACCEPTED
```

This does **not** mean overall V1 is complete. Overall V1 remains open until V1.2 proves the historical compatibility path and exact semantic parity.

---

## §2 Authority and anchors

Read current checked-in versions in this order before implementation.

1. `Docs/Architecture/AUTHORITY.md`
   - source precedence;
   - immutable revision authority;
   - source/evidence freshness;
   - compatibility/history rules.

2. `Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md`
   - KnowledgeSpace / KnowledgeRevision;
   - Entity + Assertion model;
   - generic scope / visibility / standing / temporal meaning;
   - DomainContract / SemanticProfile boundary;
   - source/evidence ownership;
   - historical compatibility posture.

3. `Docs/Architecture/ARCHITECTURE-vnext-read-path-and-performance.md`
   - `ParsedKnowledgeRevision` responsibilities;
   - derived revision-local indexes;
   - immutable internal representation;
   - bounded-read target shape;
   - safe/unsafe cache rules.

4. `Docs/Roadmaps/ROADMAP.md` — V1 in particular.

5. Frozen V0.1 provider contract:

   ```text
   Docs/Contracts/vnext/dm_vnext_contract_v1.json
   src/dungeonmind/contracts/vnext/
   ```

6. Current historical normalization/read implementation, for lessons rather than API preservation:

   ```text
   src/dungeonmind/application/graph_snapshot.py
   src/dungeonmind/application/parsed_revision_cache.py
   src/dungeonmind/application/world_graph_read_context.py
   ```

7. `CONTRIBUTING.md`
   - import boundaries;
   - no `dungeonmind_dnd` dependency from generic Kernel;
   - versioned durable-contract discipline;
   - standard gates.

8. Existing V0 generic fixtures:

   ```text
   tests/fixtures/vnext/organizational_memory_v1.json
   tests/fixtures/vnext/temporal_supersession_v1.json
   tests/fixtures/vnext/adversarial_epistemic_identity_v1.json
   ```

Repository truth outranks this handoff. If current checked-in architecture contradicts a detail here, STOP and rebrief rather than silently choosing the handoff.

---

## §3 Scope

### In scope

1. Add an application-layer vNext normalization module, preferred location:

   ```text
   src/dungeonmind/application/vnext/
   ```

2. Define genuinely immutable internal records for the frozen generic primitives needed by bounded reads:
   - entity identity;
   - assertion identity/subject/predicate/value;
   - assertion generic governance metadata;
   - identity aliases;
   - evidence refs;
   - exact revision/domain/profile identity.

3. Add a pure builder that consumes:
   - one validated `KnowledgeRevision`;
   - already-decoded vNext `Entity`, `Assertion`, `IdentityAlias`, and `EvidenceRefV3` values (or an equivalent internal decoded-content input);
   - no repositories, files, clocks, network, database, profile execution, or source-authority reads.

4. Produce one `ParsedKnowledgeRevision` with deterministic immutable mappings/indexes equivalent to:

   ```text
   entities_by_id
   assertions_by_id
   aliases_by_id
   evidence_by_id

   assertions_by_subject
   entity_ref_outgoing
   entity_ref_incoming
   entity_adjacency

   assertion_evidence
   evidence_supporters

   alias_exact_index
   literal_exact_index
   lexical_candidate_index
   ```

   Names may differ. Responsibilities may not.

5. Keep lookup indexes domain-agnostic.

   For example, the Kernel may index:

   ```text
   (predicate, canonical literal JSON) -> assertion IDs
   normalized alias text -> entity IDs
   token -> structural candidate assertion/entity IDs
   ```

   It must **not** decide that a predicate means "name", "NPC", "location", "campaign", or another domain concept.

6. Enforce generic structural integrity while building the model:
   - duplicate entity/assertion/alias/evidence IDs fail closed;
   - every assertion subject entity exists;
   - every `EntityRefValue` target entity exists;
   - every assertion evidence ref points to an evidence record in the decoded revision content;
   - every alias entity exists;
   - every alias evidence ref exists;
   - index rows may not silently reference missing primary records.

7. Make all nested JSON-bearing values safe against cache/read poisoning.

   The parsed representation must not retain caller-owned mutable dict/list/model references.

   Acceptable mechanisms include:
   - recursively frozen JSON values;
   - canonical JSON text/bytes for literal/domain payloads plus deterministic thawing later;
   - another truly immutable internal form.

   A merely `frozen=True` outer model containing mutable nested dict/list objects is not sufficient.

8. Make index construction deterministic regardless of input sequence order.

9. Add one deterministic 10k generic benchmark/characterization lane for:
   - normalized-model build;
   - exact entity lookup;
   - subject-assertion lookup;
   - adjacency lookup;
   - evidence-supporter lookup;
   - alias/literal/lexical candidate lookup where implemented;
   - peak traced memory.

10. Record the benchmark artifact under `Docs/Benchmarks/` with exact workload identity, semantic digest, cardinalities, build timing, lookup timing, and memory observation.

### Out of scope — falsification

This PR must **not**:

- decode `dm_union_graph_v1` through `dm_union_graph_v6` into the new model;
- change or delete current historical graph readers;
- invent bridge-genesis migration;
- create or migrate a durable KnowledgeSpace;
- add PostgreSQL tables/repositories/migrations;
- change current World Graph read/write services;
- add `KnowledgeReadContext`;
- perform scope admission;
- perform visibility admission;
- resolve or execute a DomainContract policy;
- resolve or execute a SemanticProfile;
- load current source lifecycle/authority state;
- cache admitted/scoped results;
- add Redis/process-global caches;
- change public retrieval APIs;
- repin DungeonMindBuddy;
- change V0 public contract models or their aggregate identity;
- add World/TTRPG fields or terms to generic Kernel code;
- claim V1, V2, V3, or performance-target completion.

V1.1 builds the immutable serving substrate. It does not yet make production reads use it.

---

## §4 Invariants that bind this slice

### 4.1 Frozen V0 contract remains frozen

The checked-in V0 bundle must still verify exactly as:

```text
contract family: dungeonmind-vnext
revision: v1
aggregate: fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea
```

V1.1 may consume those contracts. It may not silently revise them.

If an implementation need appears to require a new public cross-repository field, STOP.

### 4.2 Parsed state is derived, never authority

The immutable revision and its content digest remain authority.

`ParsedKnowledgeRevision` and every index are:

```text
rebuildable
revision-local
discardable
non-authoritative
```

Deleting the parsed/index representation and rebuilding it from the same verified decoded content must produce the same semantic result.

### 4.3 No admission in the parser

V1.1 must preserve all valid decoded assertions regardless of:

```text
scope
visibility
standing
focus
domain policy
source current lifecycle state
```

The parser may validate structural contract integrity. It may not decide what a caller is allowed to see.

`retracted` assertions remain represented. V2/V3 admission decides whether a request sees them.

### 4.4 Referential integrity fails closed

Missing structural references do not become partial success.

At minimum fail on:

```text
assertion subject entity missing
entity-ref target missing
assertion evidence ref missing
alias entity missing
alias evidence ref missing
duplicate stable IDs
```

Do not fabricate placeholder entities/evidence to make indexing easier.

### 4.5 Internal immutability is real

The built parsed revision must not be poisonable by:

- mutating an input Pydantic model after build;
- mutating an input literal JSON dict/list after build;
- mutating an input domain-metadata payload after build;
- mutating an input temporal-domain payload after build;
- mutating a caller-owned list used to construct the builder input;
- assigning into an exposed index mapping/list.

Use fresh copies + immutable storage. Do not rely on callers behaving well.

### 4.6 Determinism

For semantically identical decoded content:

```text
input order A
input order B
```

must yield:

```text
same normalized semantic digest
same index memberships
same stable ordering inside index values
```

The benchmark may report timings separately, but semantic identity must be exact.

### 4.7 Indexes remain generic

Entity-valued assertions may drive adjacency because `EntityRefValue` is a Kernel contract.

Alias text may drive alias lookup because `IdentityAlias` is Kernel identity machinery.

Literal/lexical indexes may index structural/canonical values generically.

The Kernel may not hard-code:

```text
dnd5e:name
dnd5e:npc
dungeonbuddy.scope:campaign
GM
PLAYER
campaign_id
session_id
```

or equivalent domain meaning.

### 4.8 No source-authority caching

Evidence refs are immutable revision content for this model.

Whether their referenced source artifact/revision is currently valid/active is **not** frozen by this parsed revision.

Do not include current source-lifecycle verdicts in `ParsedKnowledgeRevision`.

### 4.9 Compatibility identity

If the slice exposes a parse/index compatibility identifier, it must include every input that can change parsing/index meaning, at minimum:

```text
internal parser/index format revision
graph schema identity
domain_contract_ref identity
semantic_profile_ref identity
```

Do not use revision ID alone as a universal compatibility key.

V1.1 does not need to land a cross-request cache; it only must not design an unsafe key that later code would naturally misuse.

---

## §5 Work plan

### Step 1 — establish the internal immutable records

Create the smallest internal record family needed to hold generic vNext knowledge without mutable nested state.

Preferred qualities:

```text
stdlib dataclass(frozen=True, slots=True)
immutable tuples/frozensets
read-only mappings built from private copies
canonical JSON representation for arbitrary JSON payloads
```

Pydantic is not forbidden, but outer-model freezing alone is not proof of nested immutability.

Do not export this internal model as a new public contract family.

### Step 2 — add the pure builder

Preferred conceptual API:

```python
build_parsed_knowledge_revision(
    revision: KnowledgeRevision,
    *,
    entities: Sequence[Entity],
    assertions: Sequence[Assertion],
    aliases: Sequence[IdentityAlias],
    evidence: Sequence[EvidenceRefV3],
) -> ParsedKnowledgeRevision
```

An equivalent typed `DecodedKnowledgeContent` input is acceptable if it makes the later V1.2 decoder seam clearer.

Important boundary:

> V1.1 is allowed to accept already-decoded/verified content. It does not need to define the final durable `graph_payload` codec or prove payload-hash verification yet.

If an internal decoded-content object carries `graph_schema` / payload-digest identity, the builder should cross-check it against `KnowledgeRevision` rather than silently accept disagreement.

Exact durable payload decoding/hash verification belongs to the decoder seam and is explicitly part of V1.2 unless current repository truth proves a smaller clean placement.

### Step 3 — build structural indexes once

Build indexes from immutable normalized records, not by retaining mutable contract objects.

Required properties:

- dictionary/map lookup by exact stable ID;
- subject assertion IDs sorted deterministically;
- entity-ref incoming/outgoing adjacency deterministic;
- touching adjacency derivable without scanning all assertions;
- evidence supporter lookup deterministic;
- alias candidate lookup deterministic;
- literal exact lookup deterministic;
- lexical candidate generation deterministic if included.

No index is allowed to collapse multiple assertions into a winner.

### Step 4 — add structural-integrity failures

Add focused tests for every fail-closed condition in §4.4.

Prefer the repository's established persistence/integrity error family where appropriate instead of inventing user-facing exception semantics unnecessarily.

### Step 5 — prove deep immutability

Tests must deliberately mutate the original input after build.

Include at least:

1. mutate original `LiteralValue.value` nested dict/list;
2. mutate original assertion `domain_metadata` JSON payload;
3. mutate original `DomainTemporalScope` payload;
4. mutate original input list order/content;
5. attempt assignment into exposed parsed mappings/index values.

The parsed semantic digest and indexed values must remain unchanged.

### Step 6 — prove deterministic reconstruction

Using generic V0 fixtures plus targeted synthetic records:

```text
ordered input
reversed input
shuffled input with fixed seed
```

must produce the same normalized digest and exact index memberships/order.

Use a digest over the normalized semantic content, not Python object repr/memory addresses.

### Step 7 — characterize 10k structural behavior

Add a deterministic generic synthetic fixture generator for 10k entities/assertions/evidence with a fixed workload identity.

Record at least:

```text
fixture/config digest
entity count
assertion count
entity-ref assertion count
evidence count
alias count
normalized semantic digest
build elapsed
peak traced memory
exact entity lookup p50/p95
subject assertion lookup p50/p95
adjacency lookup p50/p95
evidence supporter lookup p50/p95
```

If alias/literal/lexical indexes are present, record their lookup lane too.

The important proof in V1.1 is structural:

> lookup touches the revision-local index rather than scanning the full revision.

Do not claim the V3 `<25 ms` / `<50 ms` public-read targets here; admission/provenance/public DTO construction do not exist yet.

### Step 8 — preserve boundaries

Add/extend tests proving:

- no generic vNext application module imports `dungeonmind_dnd`;
- no database/API/agent dependency enters the new module;
- current public World read/write modules are unchanged;
- V0 bundle generation/check remains exact.

---

## §6 Acceptance gates

At minimum, return exact output for:

```bash
uv sync

uv run pytest -q tests/unit/test_vnext_parsed_knowledge_revision.py
uv run pytest -q tests/unit/test_import_boundaries.py
uv run pytest -q
uv run pytest -m conformance

uv run ruff check .
uv run pyright

uv run python scripts/generate_vnext_contract_bundle.py --check

git diff --check
```

Use the actual focused test path if implementation chooses a nearby conventional name.

Because this slice must not touch repositories/storage, a new PostgreSQL integration behavior is not expected. Existing CI integration gates still must not regress; report repository CI truth honestly.

### Focused acceptance matrix

The focused V1.1 suite must prove at least:

1. exact `KnowledgeRevision.space_id` and `revision_id` are preserved;
2. exact `DomainContractRef` is preserved;
3. exact `SemanticProfileRef` is preserved;
4. entities are retrievable by exact ID;
5. assertions are retrievable by exact ID;
6. aliases are retrievable by exact ID;
7. evidence refs are retrievable by exact ID;
8. subject -> assertions index is complete and deterministic;
9. incoming entity-ref adjacency is complete and deterministic;
10. outgoing entity-ref adjacency is complete and deterministic;
11. touching adjacency does not require a whole-revision scan after build;
12. assertion -> evidence index is exact;
13. evidence -> supporter assertions index is exact;
14. alias exact index preserves ambiguity instead of selecting a winner;
15. literal exact index preserves multiple matching assertions instead of selecting a winner;
16. lexical candidate index, if present, is deterministic and non-authoritative;
17. duplicate entity ID fails closed;
18. duplicate assertion ID fails closed;
19. duplicate alias ID fails closed;
20. duplicate evidence ID fails closed;
21. missing assertion subject fails closed;
22. missing entity-ref target fails closed;
23. missing assertion evidence fails closed;
24. missing alias entity fails closed;
25. missing alias evidence fails closed;
26. established/provisional/retracted assertions all remain represented;
27. scope/visibility metadata is preserved but not applied;
28. arbitrary canonical literal JSON round-trips semantically;
29. arbitrary domain metadata JSON round-trips semantically;
30. arbitrary domain temporal JSON round-trips semantically;
31. mutation of original Pydantic input cannot change the parsed model;
32. mutation of original nested JSON cannot change the parsed model;
33. exposed parsed mappings/index collections cannot be mutated;
34. reordered input builds the same semantic digest;
35. reordered input builds exactly the same index memberships/order;
36. generic organizational-memory fixture can build without TTRPG imports;
37. adversarial epistemic/identity fixture can build without collapsing conflicts;
38. no public V0 contract schema changes;
39. V0 aggregate remains exactly `fd04a904...`;
40. 10k benchmark artifact is generated and records semantic digest before timings.

### Benchmark command

Prefer a dedicated command, for example:

```bash
uv run python benchmarks/vnext_parsed_knowledge_revision.py --size 10000
```

The exact CLI may differ. It must be deterministic and documented.

---

## §7 Stop conditions

STOP and return a design report instead of coding around any of these:

1. `ParsedKnowledgeRevision` cannot be made truly immutable without retaining mutable public contract objects.
2. A required structural index needs World/TTRPG ontology knowledge.
3. Building core indexes requires executing a DomainContract policy.
4. Building core indexes requires executing a SemanticProfile.
5. Building core indexes requires current source lifecycle/authority reads.
6. V1.1 requires changing a frozen public vNext contract or the V0 aggregate.
7. A new durable graph payload schema must be invented to answer the V1.1 question. If so, stop and decide whether that schema belongs in this slice or requires a contract amendment; do not smuggle it in as an internal dict convention.
8. Historical v1-v6 revisions must be rewritten in place.
9. Existing `ParsedGraphSnapshot` must be changed in a way that risks current production World reads merely to make the new model easier.
10. A global/process-wide cache becomes necessary to demonstrate lookup behavior.
11. An index would become the only copy of information rather than rebuildable derived state.
12. Index construction collapses conflicting assertions, aliases, relationships, or evidence into one winner.
13. The 10k benchmark can only meet a desired number by skipping structural integrity checks or changing semantics.
14. V0 final acceptance/merge has not actually happened when implementation is about to begin.

Required stop report:

```text
Stop condition:
Exact authority/fixture affected:
Expected V1.1 model:
Observed conflict:
Why local workaround would violate an invariant:
Options considered:
Recommended architecture/roadmap change:
Impact on V1.2/V2/V3:
```

---

## §8 Handback requirements

Return all of the following.

### Repository identity

```text
repository
branch
exact base SHA
exact head SHA
PR number/status
activation Steward-sync anchor
V0 final Buddy merge/acceptance anchor
```

### Primary answer

State explicitly:

```text
Can already-decoded generic vNext knowledge be represented as one immutable,
deterministic, revision-local indexed model without admission or domain meaning?

YES / NO
```

### Internal model decision

Document:

- exact internal record shape;
- how arbitrary canonical JSON is frozen;
- how it is later thawable without semantic loss;
- how immutable mappings/indexes are exposed;
- whether a parse/index compatibility ID exists and exactly what it covers.

### Index ledger

For every landed index record:

```text
index name
key shape
value shape
build source
why it is domain-agnostic
why it is derived/rebuildable
consumer expected in V2/V3/V4
```

### Integrity proof

Report every fail-closed case from §6 and exact focused-test result.

### Immutability proof

Report the mutation attempts and resulting stable semantic digest.

### Determinism proof

Report:

```text
ordered digest
reversed digest
shuffled digest
index parity result
```

### Performance characterization

Link the checked-in benchmark artifact and report:

```text
10k workload digest
build timing
peak memory
lookup p50/p95 lanes
cardinalities
semantic digest
```

Do not extrapolate to 100k if it was not run.

### Contract/boundary proof

Report:

```text
V0 aggregate before/head
bundle --check result
import-boundary result
whether any current World application/public read path changed
```

Expected:

```text
aggregate remains fd04a904...
no current World read/write path change
```

### What remains false after V1.1

Even after success:

- overall V1 is not complete;
- legacy `dm_union_graph_v1`–`v6` do not yet decode into `ParsedKnowledgeRevision` through the new compatibility seam;
- durable vNext `graph_payload` codec/hash verification is not yet proven unless explicitly and separately accepted;
- no production repository loads this model;
- no cross-request parsed revision cache is required/landed by this slice;
- no `KnowledgeReadContext` exists;
- no generic/domain admission runtime uses the model;
- no bounded public read uses these indexes;
- no current World read path is replaced;
- no source-authority freshness behavior changes;
- no vNext durable KnowledgeSpace exists;
- no migration/bridge genesis exists;
- no V3 public-read latency target is claimed;
- no cutover has happened.

### Named successor

The next slice is:

```text
V1.2 — legacy v1-v6 compatibility decoder -> ParsedKnowledgeRevision
```

Primary successor question:

> Can every currently supported immutable `dm_union_graph_v1` through `v6` revision be decoded through a quarantined compatibility boundary into the accepted V1.1 normalized model with exact current semantic parity and fail-closed malformed-history behavior, without making historical schemas the new hot-path model?

If legacy World semantics cannot map into the generic internal model without importing active DungeonBuddy/D&D meaning into the Kernel, V1.2 must STOP and rebrief the compatibility-package boundary rather than contaminate V1.1.
