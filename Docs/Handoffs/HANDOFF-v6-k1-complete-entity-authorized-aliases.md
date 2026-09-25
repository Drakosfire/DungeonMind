# HANDOFF — V6.K1 authorized identity aliases in complete entity reads

**Created:** 2026-09-24
**Status:** COMPLETE — `V6_K1_COMPLETE_ENTITY_AUTHORIZED_ALIASES_ACCEPTED`
**Implementation repository:** `Drakosfire/DungeonMind`
**DungeonMind base:** `6edb9e40d1dc930f537c66deb1afbd1b99002844` — merged PR #75
**Consumer:** `Drakosfire/DungeonMindBuddy`
**Accepted Buddy V6.1:** PR #749, merge `7a63c8b39937776ddede24d3d76001ef59fd37c4`
**Frozen V0 aggregate:** `fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`
**Suggested branch:** `kernel/v6-k1-complete-entity-authorized-aliases`
**Suggested PR title:** `KERNEL: authorize aliases in vNext complete-entity reads`
**Next consumer step:** DungeonMindBuddy V6.2 — complete-object read adaptation + World-object DTO preservation
**Acceptance token:** `V6_K1_COMPLETE_ENTITY_AUTHORIZED_ALIASES_ACCEPTED`
**Substantive reviewed head:** `91d2ebaf8aadf512a26ac209cfe8f6414063e732` — PASS review `5321738653`
**Merge:** PR #76, `f3738f3af3e3c8e204668a3d87d240a32c0d3988`

## 1. Mission

Answer one question:

> Can an exact vNext complete-entity read return the selected entity's authorized identity aliases with work proportional to that entity and its alias support, while preserving generic fail-closed source/evidence semantics and without inventing alias scope, visibility, domain-policy, or public alias-search semantics?

DungeonBuddy V6.1 now has the correct domain runtime. V6.2 needs to map native `get_complete_entity()` results into the existing complete World-object product DTO.

That DTO exposes aliases. The vNext parsed revision contains raw `IdentityAlias` records, but `CompleteEntityLookupResult` does not return them. V4.3 explicitly ruled that consumers may not treat structural alias indexes as public authority or assume aliases are public by default.

Therefore Buddy must not scan raw alias state and invent its own authorization rule. This is a Kernel read-contract completion.

## 2. Architecture ruling

`IdentityAlias` remains Kernel identity machinery:

```text
IdentityAlias
  alias_id
  entity_id
  alias_text
  evidence_ref_ids
  standing
```

It is not an ordinary domain assertion.

The frozen contract has no alias-level:

```text
scope
visibility
claim_mode
temporal_scope
domain_metadata
```

Do not invent them.

A domain-specific nickname/title/codename/secret name that needs scope or visibility belongs in an ordinary assertion, not `IdentityAlias`.

### Alias authorization for exact complete reads

An alias is returned only when:

```text
alias.entity_id == selected entity
alias.standing is in request.standing_selector
every alias evidence dependency passes generic source/evidence integrity
```

Alias evidence uses the same checks as assertion evidence:

```text
evidence exists
evidence annotation schema declared
source artifact exists
source visibility passes request audience
source status == active
source annotation schemas declared
named source revision exists
source revision belongs to the exact artifact
```

If any required support fails, exclude the alias.

An evidence-less alias is permitted by the frozen contract and may be returned by standing alone.

`DomainAdmissionPolicy.narrow()` remains assertion-oriented. Do not fake an assertion to run an alias through it. Identity aliases are generic Kernel identity truth.

## 3. This does not authorize alias search

V4.3 remains binding.

This PR only supports:

```text
exact entity ID
→ complete entity read
→ authorized aliases for that already-selected entity
```

Do not modify:

```text
SearchReadService
public alias-backed search
alias lexical discovery
fuzzy alias lookup
```

## 4. Revision-local alias index

Current parsed state has:

```text
aliases_by_id
alias_exact_index
```

Neither provides local enumeration by selected entity without scanning aliases.

Add rebuildable deterministic derived state:

```text
aliases_by_entity:
  entity_id -> tuple[alias_id, ...]
```

Required properties:

- deterministic;
- alias IDs sorted;
- deeply immutable;
- rebuildable from revision content;
- non-authoritative;
- exact entity alias lookup never scans unrelated aliases.

Provide helpers equivalent to:

```text
get_entity_alias_ids(entity_id)
get_entity_aliases(entity_id)
```

Exact naming is implementation latitude.

Do not change the frozen `IdentityAlias` contract.

## 5. Reuse generic evidence admission

Do not duplicate the assertion evidence/source gate.

Refactor the existing generic evidence-chain logic only as needed so both assertions and aliases can reuse one evidence-ref check, conceptually:

```text
evidence_refs_pass(
  evidence_ref_ids,
  parsed,
  provenance,
  audience,
  declared_labels,
  domain_contract,
  memo,
) -> reason | None
```

Then existing assertion admission delegates to this helper unchanged in meaning, and complete-entity alias admission uses the same helper.

Regression requirement: existing assertion admission semantics and digests remain unchanged.

## 6. Complete result shape

Extend the application-layer complete result, not frozen V0 contracts.

Preferred:

```text
CompleteEntityLookupResult
  ...
  related_entities
  aliases: tuple[ParsedIdentityAlias, ...]
```

Only authorized aliases appear.

Do not broaden basic `get_entity()` unless implementation evidence requires consistency. Acceptance requires complete reads only.

Alias ordering: deterministic `alias_id` ascending.

## 7. Support closure

If a returned alias depends on evidence, complete-read support must include it.

The returned:

```text
evidence
source_artifacts
source_revisions
```

becomes the deterministic union of support for:

```text
admitted assertions
+
returned aliases
```

No duplicates.

Alias-only evidence must not disappear merely because no admitted assertion references it.

This is required so Buddy V6.2 can build provenance bindings without reaching into raw Kernel state.

## 8. Provenance coherence

Alias support may require source IDs that assertion admission did not load.

Any additional source lookup must use the already-pinned coherent:

```text
context.source_reader
```

It is acceptable to use one additional targeted provenance snapshot for alias-only support.

Do not:

```text
open a new source epoch
scan all sources
load all revisions
read mutable source state outside the pinned context
```

Record provenance snapshot counts.

## 9. Standing, completeness, and privacy

Standing:

```text
established alias + [established] → eligible
provisional alias + [established] → excluded
provisional alias + [established, provisional] → eligible
retracted alias + selector excluding retracted → excluded
```

Aliases excluded by normal standing/source/evidence admission do not make a complete read partial; they are not admitted truth for that request.

`CompleteEntityLookupResult.result_digest` must bind returned aliases, including:

```text
alias_id
entity_id
alias_text
standing
evidence_ref_ids
```

A returned alias change changes the digest.

An excluded/hidden alias must not perturb the visible result digest.

## 10. Work accounting

Add enough work accounting to prove locality, preferably:

```text
alias_candidates
aliases_returned
alias_evidence_ids_consulted
```

Avoid redundant counters if existing ones can express the same work exactly.

Required structural witness:

```text
selected entity has 2 aliases
revision has 10,000 aliases for unrelated entities
→ alias candidate work remains 2
```

Timing alone is insufficient.

## 11. Acceptance witnesses

### Established evidence-backed alias

```text
entity:person:ada
alias:
  alias_id = alias:ada
  entity_id = entity:person:ada
  alias_text = Ada
  standing = established
  evidence_ref_ids = [ev:ada]
```

With active visible support:

```text
get_complete_entity(...)
→ alias returned
→ alias evidence returned
→ exact source artifact/revision support returned
```

### Hidden-source alias

Same alias, source visibility not satisfied:

```text
entity may still be found
alias not returned
alias-only support not returned unless required by other admitted material
hidden alias does not affect visible digest
```

### Provisional alias

Established-only request excludes it; established+provisional request returns it.

### Evidence-less alias

Established alias with no evidence is returned without source work.

### Locality

Large revision with unrelated aliases proves no full alias scan.

### Genericity

Include a non-TTRPG example such as an organizational identity alias. No Buddy vocabulary may enter Kernel runtime.

## 12. Compatibility obligations

Must remain unchanged:

```text
V0 frozen aggregate
V1 normalized semantic authority
V2 assertion admission semantics
V3 existing assertion/relationship complete-read semantics
V4.1 neighborhood
V4.2 evidence/anchors
V4.3 search semantics
V5 governed writes/publication
legacy compatibility readers
```

If adding `aliases_by_entity` changes a parsed compatibility/format key, document it as derived-index compatibility identity, not semantic authority drift.

No historical revision rewrite.

## 13. First commit — control-plane repair

DungeonMind `main` is runtime-current through merged PR #75, but checked-in roadmap/stewardship text still contains stale pre-acceptance V5.4 state.

Before runtime work, record:

```text
V5.4 COMPLETE
V5_4_PROSPECTIVE_REFERENCE_PUBLICATION_ACCEPTED
accepted head:
  c7700f98e62732cbd1c021270f5366a77c24ea9b
final PASS:
  5296514025
merge:
  6edb9e40d1dc930f537c66deb1afbd1b99002844

V5 COMPLETE
V6 consumer/domain implementation ACTIVE
```

Update:

```text
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
Docs/Roadmaps/ROADMAP.md
Docs/Handoffs/HANDOFF-v5-4-prospective-reference-allocation-substitution.md
```

### Link the post-cutover performance successor

Also make durable the accepted roadmap decision that the vNext migration roadmap is finite.

Add:

```text
Docs/Roadmaps/ROADMAP-post-vnext-performance.md
```

Update current V11 to:

```text
Post-cutover performance baseline + optimization handoff
```

Predecessor exit:

```text
POST_CUTOVER_PERFORMANCE_BASELINE_ACCEPTED
VNEXT_ROADMAP_COMPLETE
```

Successor first phase:

```text
O1 — Hot-path work elimination
```

Successor phase sequence:

```text
O1 redundant-work elimination
O2 resident immutable serving state
O3 serialization/hash/materialization
O4 write amplification
O5 physical storage experiments if evidence still justifies them
O6 production-scale concurrency/operational tuning
O7 performance lock-in
```

Update the Steward completion condition so a successor Steward handoff activates after V11.

Do not implement optimization work in this PR.

## 14. Expected changed surface

Control plane:

```text
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
Docs/Handoffs/HANDOFF-v5-4-prospective-reference-allocation-substitution.md
Docs/Handoffs/HANDOFF-v6-k1-complete-entity-authorized-aliases.md
Docs/Roadmaps/ROADMAP.md
Docs/Roadmaps/ROADMAP-post-vnext-performance.md
```

Runtime, approximately:

```text
src/dungeonmind/application/vnext/model.py
src/dungeonmind/application/vnext/builder.py
src/dungeonmind/application/vnext/admission.py
src/dungeonmind/application/vnext/entity_reads.py
src/dungeonmind/application/vnext/__init__.py
```

Tests:

```text
tests/unit/test_vnext_parsed_knowledge_revision.py
tests/unit/test_vnext_entity_reads.py
tests/unit/test_vnext_evidence_reads.py   # regression if helper refactored
```

Do not change:

```text
src/dungeonmind/contracts/vnext/**
```

## 15. Explicitly out of scope

Do not implement:

```text
alias search
alias scope/visibility fields
alias domain-policy hooks
Buddy World-object DTO mapping
Buddy production routes
WorldKeeper changes
bridge-genesis migration
live authority migration
cutover
write-path alias changes
merge/split changes
performance phases O1–O7
```

## 16. Stop conditions

Stop and rebrief if:

- correct alias authorization requires frozen `IdentityAlias` scope/visibility fields;
- aliases require assertion-oriented domain policy;
- alias evidence cannot reuse generic source/evidence semantics;
- local alias enumeration requires authoritative durable state;
- alias-only support cannot be returned without changing accepted evidence meaning;
- Buddy/TTRPG vocabulary is required in Kernel code;
- frozen V0 aggregate must change;
- alias search is required to satisfy complete reads.

Required report:

```text
Stop condition:
Observed evidence:
Accepted assumption that failed:
Why local compensation is unsafe:
Kernel vs consumer ownership:
Recommended rebrief:
What remains safe in parallel:
```

## 17. Verification

Run:

```text
uv run ruff check .
uv run pyright

uv run pytest -q   tests/unit/test_vnext_parsed_knowledge_revision.py   tests/unit/test_vnext_entity_reads.py   tests/unit/test_vnext_evidence_reads.py   tests/unit/test_vnext_search.py

uv run pytest -m "not integration"

git diff --check
```

Run repository CI.

If the inherited benchmark-smoke failure remains:

```text
benchmarks/world_graph_reads.py
WorldGraphProjectionService.__init__()
missing reviewed_world_initializations
```

classify it exactly. Do not call overall CI green.

## 18. Acceptance matrix

PASS requires:

1. deterministic `aliases_by_entity`;
2. no unrelated alias scan;
3. authorized aliases returned on complete read;
4. standing enforced;
5. referenced evidence must exist;
6. evidence annotation declarations enforced;
7. source visibility enforced;
8. source active status enforced;
9. source annotation declarations enforced;
10. source revision identity enforced;
11. evidence-less established alias supported;
12. alias-only evidence/source support returned;
13. deterministic alias ordering;
14. digest binds returned aliases;
15. hidden aliases do not perturb visible digest;
16. non-TTRPG witness passes;
17. existing V3 complete-read assertion/relationship semantics unchanged;
18. V4.3 alias search remains disabled;
19. frozen V0 aggregate unchanged;
20. no Buddy vocabulary in Kernel;
21. no product/WorldKeeper routing changes;
22. exact-head CI classified.

## 19. Handback

Return:

```text
base / exact head / branch / PR
commits
changed paths

aliases_by_entity shape
lookup locality proof
alias admission rule
evidence/source reuse strategy
provenance snapshot counts

positive / hidden / standing / evidence-less witnesses
10k unrelated-alias locality witness
genericity witness
digest non-interference proof

ruff
pyright
focused tests
non-integration suite
CI
inherited failures

what remains false
named successor
```

## 20. Acceptance and successor

Steward substantive review `5321738653` recorded and PR #76 merged:

```text
V6_K1_COMPLETE_ENTITY_AUTHORIZED_ALIASES_ACCEPTED
```

Acceptance means an exact complete-entity read can expose Kernel-authorized identity aliases without consumer-side authority invention.

It does **not** authorize alias search.

After acceptance, return to DungeonMindBuddy:

```text
V6.2 — vNext complete-object read adaptation + World-object DTO preservation
```

V6.2 may then map:

```text
CompleteEntityLookupResult
+ authorized aliases
+ pinned Buddy KnowledgeReadContext
+ coherent targeted provenance
→ existing WorldGraphObjectProjectionResult
```

Production route switching remains later.
