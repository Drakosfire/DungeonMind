# ADR-0018 — Relationship endpoint aspects v6

**Status:** Accepted  
**Date:** 2026-08-15  
**Deciders:** implementing agent, per CUTOVER dual-sense dispatch after DungeonMindBuddy PR #588  
**Supersedes:** none  
**Related:** ADR-0014, ADR-0017, `dm_union_graph_v5`, `vocabularies/world-object-v5.json`, DungeonMindBuddy PR #588

## Question

How does DungeonMind represent the three Eldyrwild dual-sense identities proven by merged Buddy PR #588 — Wizard College as location and organization, Meat Distribution Network as party and site, Hempholm Folk Revelry as group and event — without splitting one world identity into two persistent objects, widening `world-object-v5` predicates, or mutating historical union-graph schemas?

## Context

Buddy PR #588 sealed `dmb_relationship_dual_sense_decomposition_v1`. It proved that five residual relationships become locally admissible when the *assigned endpoint* uses a secondary kind, while retained primary-sense relationships remain admissible only if the original primary kind is kept. Those are two assertion-scoped senses of **one identity**, not two identities and not a predicate-widening problem.

Historical `dm_union_graph_v1`–`v5` payloads and readers are immutable. `world-object-v5` already contains the needed kinds and predicates; the gap is representation: a relationship cannot currently name which admitted sense of an endpoint it uses.

Whole-world Eldyrwild adoption, durable aspect assertion minting, repository writes, and CUTOVER readiness are out of scope. This decision establishes representability and a deterministic D&D materialization *plan* only.

## Decision

1. **Publish additive `dm_union_graph_v6`.** v1–v5 remain immutable. A v6 object keeps one primary `kind` and may carry zero or more assertion-scoped secondary kind aspects.
2. **A secondary kind is an aspect of one object identity**, not a companion object, not `IdentityDecisionKind.SPLIT`, and not a `kinds: list[str]` field.
3. **Relationships select aspects through exact admitted aspect assertion IDs**, never `aspect_key` lookup. Either endpoint may name one aspect; omitted refs fall back to the object's primary kind.
4. **Aspect assertions carry full `KnowledgeAssertionMetadataV1`** and join the graph-global assertion-ID uniqueness set with existence, alias, summary, property, and relationship assertions.
5. **Dual-assertion scoping:** a relationship that names an aspect is visible only when both its own assertion and the referenced aspect assertion are admitted. An unrelated hidden aspect does not hide primary-sense relationships. Public dumps and `public_coverage_gaps_for_exclusion` must not leak hidden aspect assertion IDs.
6. **Kernel vs D&D split.** The kernel reader/scoper owns representation and `effective_endpoint_kind`. The D&D profile owns predicate domain/range validation against an explicit `world-object-v5` pin. The kernel does not import `dungeonmind_dnd`; the adapter does not import Buddy.
7. **Mandatory top-level discriminator** `relationship_endpoint_aspect_schema = dm_relationship_endpoint_aspect_v1` prevents a v5 payload from being silently relabeled as v6.
8. **The #588 adapter emits `DndRelationshipAspectMaterializationPlanV1` only.** It hashes package bytes itself, independently recomputes local admission, and does not invent durable aspect assertion IDs or evidence metadata.
9. **Whole-world adoption and Eldyrwild publication are deferred.** After this change, dual-sense semantics are representable; CUTOVER stays not ready; Buddy relationship STOPs stay uncleared.

## Rejected alternatives

```text
synthetic object per aspect
  rejected: falsely splits one world identity

object kinds: list[str]
  rejected: cannot express assertion-grain source/evidence/scope or edge choice

relationship-only kind override
  rejected: creates an ungrounded semantic claim detached from object authority

predicate endpoint widening
  rejected: would make semantically false relationships globally admissible

mutate dm_union_graph_v5
  rejected: historical graph schemas are immutable

IdentityDecisionKind.SPLIT
  rejected: #588 proves dual sense, not two identities

whole-world adoption in this PR
  rejected: combines representation with live durable migration/publication
```

## Consequences

DungeonMind can represent the exact #588 mapping as three aspect directives and five endpoint directives without minting new object IDs. A later adoption PR consumes the plan, attaches source-grounded assertion metadata, and publishes Eldyrwild. Historical v1–v5 readers continue to reject v6-only fields (`extra=forbid`).

## Reversal path

```text
stop publishing v6
continue reading historical v1-v5 unchanged
supersede with v7/new aspect contract if semantics later change
never reinterpret existing v6 bytes in place
```
