# ADR-0006 — Pinned profile create-or-connect contribution planning

**Status:** Accepted (PR B.2d)
**Date:** 2026-08-01
**Deciders:** B.2d implementing agent, per operator dispatch
**Supersedes:** none
**Extends:** ADR-0005 (executable D&D profile boundary)
**Related:** ADR-0004 (semantic profile boundary),
`src/dungeonmind_dnd/application/contribution_planning.py`,
`src/dungeonmind_dnd/contracts/contribution_planning.py`,
`tests/unit/test_import_boundaries.py`

## Question

How may a validated D&D Threat candidate packet be reconciled against one
exact immutable graph revision and expressed as a reviewable contribution
preview — without repository access, durable identity decisions, fuzzy
matching, graph materialization, or publication?

## Context

B.2c established a strict, provenance-bearing Threat candidate packet and
authoritative catalog validation. The kernel already owns immutable graph
revisions, a durable `GraphContribution` envelope, and identity-decision
contracts. What was missing is the non-mutating bridge: verify explicit
existing-object references, propose create-or-connect identity outcomes
from exact label/alias matches only, and emit a candidate-only contribution
preview pinned to the expected parent revision.

Durable contracts intentionally separate concerns: `GraphContribution` is a
write ledger unit without an expected-parent pin; `IdentityDecisionRecord`
is a confirmed decision, not a proposal; publication requires exact
expected-parent CAS. B.2d therefore adds a profile-owned planning envelope
rather than mutating those kernel contracts.

## Decision

1. **Graph-aware D&D planning is allowed only over a passed exact stored
   revision.** The caller fetches one `StoredGraphRevision` and supplies a
   configured `GraphSnapshotReader`. The planner never looks up current head.
2. **The profile package remains repository-blind.** Planning modules may
   import a narrowly expanded kernel surface
   (`graph_snapshot`, `contribution`, `graph`, `identity`, `vocabulary`,
   plus the B.2c allowlist) but never repositories, infrastructure, service,
   or agents. Existing B.2c modules retain the narrow allowlist.
3. **The planner parses the complete stored payload itself.** Caller-scoped
   `ParsedGraphSnapshot` inputs are forbidden: a scoped graph could hide an
   existing object and produce a false `provisional_new`.
4. **Exact label/alias matching is blocking evidence, not final authority.**
   Normalization is `term.casefold().strip()` only. No fuzzy, semantic,
   embedding, LLM, confidence, summary-based, or relationship-inferred
   matching exists.
5. **Exact same-kind singleton → proposed `resolved_existing`.** No match →
   deterministic `provisional_new` (`obj:<32 hex>` from packet digest +
   candidate id; base revision deliberately excluded so replanning does not
   churn proposed IDs). Ambiguity and any cross-kind exact match block the
   whole plan.
6. **Explicit existing IDs are verified directly and never substituted.**
   Missing or kind-mismatched references block. They never become
   `provisional_new` and never fall back to label matching.
7. **Existing relationship triples block.** Assertion-scoped evidence
   augmentation is not designed; silent merge is forbidden.
8. **A ready plan contains a candidate-only `GraphContribution` preview.**
   Every assertion is `candidate`, `gm`, `asserted`, evidenced; identity
   decision IDs, unresolved mentions, and diagnostics stay empty. Blocked
   plans carry no contribution.
9. **The plan pins the exact expected parent revision**
   (`expected_parent_revision_id == base_revision_id`) without checking
   current head. Future commit remains responsible for stale-parent CAS.
10. **No `IdentityDecisionRecord` is created.** No repository append,
    materialization, or publication occurs. Proposed object IDs are stable
    across replanning but are not canonical before confirmation. All output
    remains GM-authoring material.

## Rejected alternatives

- Kernel generic planner / interpretation layer
- Scoped snapshot planning
- Repository lookup from the profile package
- Fuzzy matching or confidence thresholds
- Automatic merge / relationship evidence augmentation
- Accepted assertions in the preview
- Direct graph save or publication
- Profile/vocabulary catalog change in this PR

## Consequences

- Same packet + same stored revision + same actor + same `planned_at` →
  byte-identical plan.
- Integrity failures (digest/world/schema/profile mismatch, malformed graph,
  ID collision) raise `DndContributionPlanningError` and produce no plan.
- Valid-but-unresolvable states yield a `blocked` plan with machine-readable
  blockers and no contribution preview.
- Successors remain explicit: B.2e durable review adoption; B.2f accepted
  materialization and CAS publication; B.3 Threat mechanics-resource binding.
