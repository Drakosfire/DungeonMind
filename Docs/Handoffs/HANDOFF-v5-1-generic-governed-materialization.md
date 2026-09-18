# HANDOFF — V5.1 generic governed materialization

**Created:** 2026-09-18
**Status:** ACTIVE — IMPLEMENTATION NOT YET ACCEPTED
**Repository:** `Drakosfire/DungeonMind`
**Implementation branch:** `kernel/v5-1-generic-governed-materialization`
**Exact branch base:** `bc115eb40f1601e5b6c6fda23ff05ee5bf06883d`
**Predecessor:** PR #68 — `KERNEL: V4.3 deterministic indexed search`
**Predecessor accepted head:** `1507248d0a8a3beeefe486b86af99aa9c2507492`
**Predecessor substantive repair:** `630d697e041a0fb18bfc970ca3eb46494e936276`
**Predecessor final Steward review:** `5250109322`
**Predecessor disposition:** `V4_3_DETERMINISTIC_INDEXED_SEARCH_ACCEPTED`
**Predecessor merge / current main:** `bc115eb40f1601e5b6c6fda23ff05ee5bf06883d`
**Frozen V0 contract aggregate:** `fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`
**Conversation provenance:** `MIND`
**PR topology:** `serial`
**One-line mission:** Given one exact native-vNext parent revision, one frozen `KnowledgeContribution`, complete `ContributionDisposition`s, and explicit publication identity inputs, deterministically materialize one validated generic child graph and one frozen `PublishKnowledgeRevisionCommand` without World/Graph-Review semantics, durable publication, head mutation, or persistence redesign.

---

# 0. Repository truth and accepted predecessor

V4 is complete.

DungeonMind now has the generic authoritative read substrate:

```text
V0   Contract freeze                                      COMPLETE
V1   Immutable normalized revision + revision indexes    COMPLETE
V2   KnowledgeReadContext + candidate admission           COMPLETE
V3   Lazy exact / complete entity reads                  COMPLETE
V4   Bounded neighborhood/evidence/anchor/search         COMPLETE
  V4.1 Bounded neighborhood                              COMPLETE
  V4.2 Evidence + anchor support                         COMPLETE
  V4.3 Deterministic indexed search                      COMPLETE
V5   Generic governed write contracts                    ACTIVE
  V5.1 Generic governed materialization                  ACTIVE
  V5.2 Expected-parent atomic CAS publication            BLOCKED ON V5.1
  V5.3 Durable idempotent replay / recovery              BLOCKED ON V5.2
```

Binding predecessor facts:

```text
PR:
  #68 — KERNEL: V4.3 deterministic indexed search

accepted exact head:
  1507248d0a8a3beeefe486b86af99aa9c2507492

substantive repair:
  630d697e041a0fb18bfc970ca3eb46494e936276

logical Steward review cycles:
  3

final PASS review:
  5250109322

disposition:
  V4_3_DETERMINISTIC_INDEXED_SEARCH_ACCEPTED

actual merge / current main:
  bc115eb40f1601e5b6c6fda23ff05ee5bf06883d

benchmark:
  Docs/Benchmarks/vnext_deterministic_search_10k_v1.json
```

The checked-in Steward/roadmap bookkeeping on that merge tip is one merge behind repository truth. This implementation PR's first commit repairs that bookkeeping and adds this handoff. It does not claim `V5_1_GENERIC_GOVERNED_MATERIALIZATION_ACCEPTED`.

---

# 1. Why this is the next slice

The full V5 roadmap question is:

> Can the current publication invariants survive after removing World/Graph-Review-specific transport shapes?

Do not answer all of that in one PR.

The old publication architecture already teaches us that three concerns are independently difficult:

```text
governed intent
→ deterministic graph materialization

materialized child
→ expected-parent atomic CAS publication

publication attempt
→ durable idempotent replay / uncertain-outcome recovery
```

V5.1 owns only the first boundary and the creation of the already-frozen command connecting it to the second.

The useful end state is:

```text
exact native-vNext parent
+ KnowledgeContribution
+ complete ContributionDisposition set
+ explicit operation identity
        ↓
generic validation
        ↓
deterministic accepted-item materialization
        ↓
canonical native-vNext child payload
        ↓
PublishKnowledgeRevisionCommand
```

There is no database write in V5.1.

That is intentional.

We should be able to prove what the generic write means before transactionality is allowed to make it durable.

---

# 2. Required bookkeeping first commit

The first commit on the implementation branch must be bookkeeping/control-plane only.

Update:

```text
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
Docs/Roadmaps/ROADMAP.md
```

and add this handoff as:

```text
Docs/Handoffs/HANDOFF-v5-1-generic-governed-materialization.md
```

Record exact predecessor truth:

```text
PR #68
accepted head:
  1507248d0a8a3beeefe486b86af99aa9c2507492

substantive repair:
  630d697e041a0fb18bfc970ca3eb46494e936276

logical review cycles:
  3

final PASS:
  5250109322

disposition:
  V4_3_DETERMINISTIC_INDEXED_SEARCH_ACCEPTED

merge:
  bc115eb40f1601e5b6c6fda23ff05ee5bf06883d
```

Suggested commit:

```text
STEWARDSHIP: complete V4.3 and activate V5.1
```

Do not include runtime implementation in that commit.

---

# 3. Required reading

Read, in order:

```text
Docs/Architecture/AUTHORITY.md
Docs/Architecture/ARCHITECTURE-domain-agnostic-governed-memory-vnext.md
Docs/Roadmaps/ROADMAP.md
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
this handoff
CONTRIBUTING.md
```

Then inspect:

```text
src/dungeonmind/contracts/vnext/contribution.py
src/dungeonmind/contracts/vnext/knowledge.py
src/dungeonmind/application/vnext/builder.py
src/dungeonmind/application/vnext/model.py
src/dungeonmind/application/vnext/records.py
src/dungeonmind/application/review_materialization.py
src/dungeonmind/application/review_materialization_v6.py
```

The World/Graph-Review materializers are evidence of the old publication seam. They are not the V5.1 implementation surface and must not be imported by the new generic path.

Do not change frozen V0 contracts.

---

# 4. Primary question

> Given one exact native-vNext parent, one frozen `KnowledgeContribution`, a complete `ContributionDisposition` set, and explicit publication identity, can DungeonMind deterministically produce one structurally validated generic child graph and one frozen `PublishKnowledgeRevisionCommand` without World/Graph-Review transport, durable publication, head mutation, or persistence redesign?

A PASS answers only that question.

---

# 5. Public API

Preferred conceptual operation:

```text
materialize_governed_revision(
    parent,
    contribution,
    dispositions,
    publication_identity,
) -> GovernedMaterializationResult
```

Exact names are implementation latitude; semantics are binding.

Inputs:

```text
parent:
  one already-built ParsedKnowledgeRevision
  graph_schema = dm_vnext_graph_v1
  exact native-vNext content (not a legacy union payload)

contribution:
  frozen KnowledgeContribution
  status = finalized
  space_id equals parent.space_id
  unique item_id set
  typed items from the frozen union only

dispositions:
  exactly one ContributionDisposition per contribution item_id
  no extras, no missing ids, no duplicate item_ids
  every disposition is accepted or rejected
  unresolved fails closed

publication identity:
  operation_ids           non-empty unique
  created_at              explicit
  expected_parent_revision_id
    must equal parent.revision_id
```

Output:

```text
GovernedMaterializationResult
  command: PublishKnowledgeRevisionCommand
  graph_payload_sha256
  accepted_item_ids
  rejected_item_ids
```

The command must satisfy the frozen parent invariant:

```text
parent_revision_id == expected_parent_revision_id == parent.revision_id
```

Command identity fields are copied from the parent except:

```text
parent_revision_id / expected_parent_revision_id  ← parent.revision_id
operation_ids                                     ← explicit input
created_at                                        ← explicit input
graph_payload                                     ← materialized child
```

`space_id`, `graph_schema`, `domain_contract_ref`, `semantic_profile_ref`, and `migration_origin_ref` come from the parent. V5.1 does not mint a child `revision_id`; that remains a later publisher concern.

The result is ephemeral. It does not write a repository, observe a head, or wrap a World/Graph-Review DTO.

---

# 6. Materialization rules

## 6.1 Validation before mutation

Fail closed, with a dedicated vNext materialization integrity error, when:

- parent is not native `dm_vnext_graph_v1`;
- contribution `space_id` disagrees with parent;
- contribution status is not `finalized`;
- contribution item ids are not unique;
- dispositions are incomplete, extra, or duplicated;
- any disposition is `unresolved`;
- publication `expected_parent_revision_id` disagrees with `parent.revision_id`;
- operation identity is empty or non-unique.

Rejected items are ignored. They must not mutate the child and must not contribute to the child payload digest.

## 6.2 Accepted-item application order

Apply accepted items in contribution `items` order.

```text
ProposeEntity
  add entity_id
  identical existing entity_id is idempotent

ProposeAssertion
  add assertion
  identical existing assertion_id is idempotent
  conflicting existing assertion_id fails closed
  referenced subject, entity-ref target, and evidence must exist in the child-so-far
  V5.1 does not invent ProposeEvidence; evidence must already be in the parent

RetractAssertion
  remove target assertion
  missing target fails closed

SupersedeAssertion
  replace target with replacement_assertion
  missing target fails closed
  if replacement assertion_id collides with a different existing assertion, fail closed

ProposeIdentityDecision
  apply only the graph-local identity kinds named in §7
  unknown or non-materializable kinds fail closed
```

After all accepted items apply, rebuild one `ParsedKnowledgeRevision` from the child primitives. Builder structural integrity is the generic validation gate. Then encode one canonical native-vNext graph payload and freeze `PublishKnowledgeRevisionCommand`.

## 6.3 Canonical child payload

The child `graph_payload` is native vNext JSON, not a World union graph:

```text
{
  "entities":   [ ... sorted by entity_id ... ],
  "assertions": [ ... sorted by assertion_id ... ],
  "aliases":    [ ... sorted by alias_id ... ],
  "evidence":   [ ... sorted by evidence_ref_id ... ]
}
```

Each array item is the frozen contract model's JSON dump. Encoding must be deterministic: same parent + contribution + dispositions + publication identity → same payload → same `canonical_sha256`.

Do not put World object/relationship bags, review ids, GM/PLAYER vocabulary, or `world_id` into the payload.

Round-trip proof:

```text
encode(child primitives)
→ contract-validate
→ build_parsed_knowledge_revision
→ success
```

The command's `graph_payload` must match that encoded payload. `graph_payload_sha256` on the result is `canonical_sha256(command.graph_payload)`.

## 6.4 Isolation

Parent `ParsedKnowledgeRevision` remains immutable. Callers must not be able to mutate the returned command payload in a way that changes the result object's recorded digest without the implementation copying on construction. Prefer deepcopy-on-read or a frozen dump, matching the old materializer's isolation discipline without copying its World types.

---

# 7. Identity handling

Identity resolution is not a V5.1 design question. Dispositions are already complete. V5.1 only applies accepted `ProposeIdentityDecision` items that have a deterministic graph-local meaning:

```text
alias_add
  require decision.alias
  add IdentityAlias
    alias_id = decision.decision_id
    entity_id = the sole subject entity
    alias_text = decision.alias
    standing = established
  subject entity must exist
  colliding alias_id fails unless identical

alias_remove
  require decision.alias
  remove aliases whose entity_id is in subject_entity_ids and alias_text matches
  matching zero aliases fails closed

merge
  retarget assertion subjects, entity-ref values, and aliases from every
  non-target subject onto the single target
  delete merged subject entities that are not the target
  all subjects and the target must exist
  leftover references to deleted entities fail closed

reject_candidate
  no graph mutation
```

Fail closed on:

```text
split
unmerge
mark_ambiguous
human_override
```

Those kinds are real frozen contract members, but applying them requires identity-rewrite policy that V5.1 does not own. Do not silently no-op them.

Do not persist identity decisions as a new payload key. The frozen native graph content remains entities, assertions, aliases, and evidence.

---

# 8. Explicitly not V5.1

Do not implement:

```text
expected-parent CAS publication
head mutation / KnowledgeHead writes
PostgreSQL / repository writes
durable receipts, idempotent replay, uncertain-outcome recovery
World Graph Review transport or review_materialization reuse
legacy union-graph child payloads
ProposeEvidence or other unfrozen item kinds
changing frozen V0 contracts
KnowledgeSpace/head storage runtime
DungeonBuddy governance workflow
current public World writer replacement
bridge-genesis migration
```

World `review_materialization*` remains the pre-cutover writer. V5.1 must not call it, wrap it, or teach tests to pass by editing it.

---

# 9. Acceptance matrix

Focused tests must prove at least:

1. Happy path: accepted `ProposeEntity` + `ProposeAssertion` against a native parent yields a command whose parent fields match the parent revision and whose child payload round-trips through the V1 builder.
2. Rejected items do not appear in the child and do not change the child digest versus an equivalent contribution that omitted them.
3. Incomplete dispositions fail closed.
4. Extra dispositions fail closed.
5. `unresolved` fails closed and produces no command.
6. Space mismatch fails closed.
7. Non-`finalized` contribution fails closed.
8. `expected_parent_revision_id` mismatch fails closed.
9. Duplicate contribution item ids fail closed.
10. `RetractAssertion` removes the target; missing target fails closed.
11. `SupersedeAssertion` replaces the target; colliding replacement id fails closed.
12. `ProposeAssertion` colliding with a different existing assertion fails closed; identical replay is idempotent.
13. Missing subject / entity-ref / evidence fails closed via generic structural validation.
14. `alias_add` / `alias_remove` / `merge` / `reject_candidate` behave as §7.
15. `split` / `unmerge` / `mark_ambiguous` / `human_override` fail closed.
16. Same inputs in different list-construction order for dispositions still yield the same command digest when coverage is identical.
17. Parent revision object is unchanged after materialization.
18. Command `parent_revision_id == expected_parent_revision_id`.
19. Organizational-memory and Buddy-shaped opaque-domain fixtures can be used as native parents without Buddy/TTRPG vocabulary entering the materializer.
20. Source of `materialization.py` / equivalent contains none of: `world_id`, `GM`, `PLAYER`, `campaign_id`, `review_materialization`, `ContributionReview`, `dungeonmind_dnd`.
21. Public export is the materialization result/function/service, not a publisher.
22. Runtime source does not claim `V5_1_GENERIC_GOVERNED_MATERIALIZATION_ACCEPTED`.
23. Large parent + one tiny accepted change characterization is recorded.
24. Frozen V0 aggregate remains `fd04a9047b8ed79aaa5e710b2247ce1b2654c0e44e05d24fafb2adecb9e7b7ea`.

---

# 10. Characterization

V5 required characterization, narrowed to V5.1 (no bytes written, no publication latency):

```text
large immutable parent
+ one tiny accepted change
```

Record:

```text
parent entity/assertion counts
accepted item count
rejected item count
child entity/assertion counts
payload bytes
parent reconstruct / materialize / validate / serialize+hash timings
```

Suggested artifact:

```text
Docs/Benchmarks/vnext_governed_materialization_10k_v1.json
benchmarks/vnext_governed_materialization_10k.py
```

The timing numbers are characterization, not a permission to weaken fail-closed validation. Structural proof is that rejected/unrelated parent mass does not change the tiny accepted child delta's meaning, and that work is a function of parent decode plus accepted-item application rather than World review machinery.

---

# 11. Intended changed surface

```text
Docs/Handoffs/HANDOFF-STEWARDSHIP-vnext-roadmap.md
Docs/Roadmaps/ROADMAP.md
Docs/Handoffs/HANDOFF-v5-1-generic-governed-materialization.md

src/dungeonmind/application/vnext/materialization.py   # expected new module
src/dungeonmind/application/vnext/errors.py            # materialization integrity error
src/dungeonmind/application/vnext/__init__.py          # public semantic export only

tests/unit/test_vnext_governed_materialization.py
benchmarks/vnext_governed_materialization_10k.py
Docs/Benchmarks/vnext_governed_materialization_10k_v1.json
```

Do not touch `src/dungeonmind/contracts/vnext/**` unless a stop/rebrief is triggered.

Do not modify current World publication to make the vNext tests pass.

---

# 12. Stop / rebrief conditions

Stop rather than compensating locally if any of these become true:

- frozen V0 contract changes are required;
- a valid child cannot be produced without `ProposeEvidence` or another new item kind;
- native child encoding requires World union-graph fields;
- generic validation requires Graph Review or Buddy governance types;
- identity kinds that V5.1 must apply cannot be defined without a new identity-resolution slice;
- a database write, head CAS, or receipt is required to make the command meaningful;
- current public World writers must change;
- V1–V4 accepted read semantics regress.

When a stop condition fires, report:

```text
Stop condition:
Roadmap phase:
Observed evidence:
Which assumption failed:
Affected authority/architecture document:
Why V5.1 cannot safely compensate:
Proposed design decision / experiment:
What remains safe in parallel:
```

Do not widen the PR silently into V5.2/V5.3.

---

# 13. Required implementation evidence

The PR handback must include:

```text
repository
branch
exact branch base
exact reviewed head
changed-file census
```

Verification must include exact commands and outcomes for:

```text
ruff
pyright / configured type checker
focused V5.1 tests
V1 index regressions
V2 admission regressions
V3 entity-read regressions
V4.1 neighborhood regressions
V4.2 evidence/anchor regressions
V4.3 search regressions
10k V5.1 materialization characterization
repository CI
```

If repository CI has an inherited failure, provide the exact traceback and prove whether the failing file/behavior is unchanged from the implementation base.

---

# 14. What remains false after V5.1

Even after successful V5.1 implementation (not yet acceptance):

```text
no expected-parent CAS publisher
no KnowledgeHead mutation
no vNext KnowledgeSpace/head persistence runtime
no durable publication receipt / replay / recovery
no World Graph Review replacement
no bridge-genesis migration
no joint DungeonMind/DungeonBuddy cutover acceptance
no current public World cutover
no historical-reader quarantine/deletion
no deeper storage redesign
```

V5.1 success means only that generic governed intent can be materialized into a validated child payload and frozen publish command.

---

# 15. Successor

After Steward records:

```text
V5_1_GENERIC_GOVERNED_MATERIALIZATION_ACCEPTED
```

V5.2 may begin: expected-parent atomic CAS publication of one already-materialized `PublishKnowledgeRevisionCommand`.

Do not begin V5.2 runtime work in this PR.
