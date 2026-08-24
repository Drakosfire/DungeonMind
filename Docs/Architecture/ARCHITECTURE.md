# DungeonMind — Architecture and Ownership

**Status:** current post-R.3 library architecture  
**Updated:** 2026-08-23  
**Authority:** this document + `AUTHORITY.md` + accepted ADRs. Where they disagree, `AUTHORITY.md` defines precedence.

## 1. Purpose

DungeonMind is an independent governed world-knowledge library for persistent fictional worlds.

Its job is to preserve and serve trustworthy world knowledge across time:

```text
sources + evidence
      │
      ▼
governed contributions / review
      │
      ▼
immutable World Graph revisions ──→ exact historical pins
      │
      ▼
scope + admissibility + provenance admission
      │
      ▼
projection / retrieval / anchors
      │
      ▼
product clients
```

DungeonMind owns knowledge semantics. A client owns what the user is doing with that knowledge.

## 2. Hard boundary: knowledge library, not agent harness

The agent harness lives outside DungeonMind.

DungeonMind does **not** own:

- model/provider selection;
- system prompts or prompt assembly;
- conversation/thread state as product state;
- tool registration or the agent tool loop;
- tool-selection policy across product capabilities;
- retries, planning loops, interruption/resume, or approvals;
- product-wide token/context budgeting;
- UI state, selected text, open documents, or current work surface.

A product such as DungeonMindBuddy may combine all of those with DungeonMind results.

DungeonMind may enforce authorization and validity for **its own operations**. For example, a write may require an exact world, parent revision, admissibility, or explicit confirmation. That is library/service authority, not ownership of an agent's complete tool set.

Existing founding-era `MindTurn`, thread, context-assembly, claim/answer-validation, and `agents/` modules are implementation facts, not automatically protected long-term library responsibilities. The architecture-fitness lane will classify them as retained library capability, separable compatibility/example surface, or retirement candidates. No new product harness behavior should be added to them while that decision is open.

Decision: [ADR-0022 — Independent library and agent-harness boundary](../Decisions/ADR-0022-independent-library-and-agent-harness-boundary.md).

## 3. Governing invariants

1. **One World Graph per world.** Campaign is scope, never a second graph.
2. **Published revisions are immutable.** One explicit head advances atomically by compare-and-swap; rollback repoints, never rewrites history.
3. **Evidence is part of knowledge validity.** Objects/assertions/relationships are admitted under the semantics of their graph schema only when their evidence chains satisfy current source/provenance rules.
4. **Reads are explicit.** Every read has one world, one selected revision, one scope, and one admissibility policy.
5. **PLAYER fails closed.** Hidden or scope-unknown material is never recovered by search, traversal, anchors, or diagnostics.
6. **Retrieval never becomes authority.** Search/ranking may narrow admitted knowledge; it may not broaden scope or manufacture truth.
7. **Durable writes are governed.** Candidate generation is not publication. Review and publication bind exact content and exact expected parent.
8. **Profiles own domain meaning.** The generic kernel owns profile identity/admission; a profile package owns its vocabulary and pure domain adapters.
9. **Clients are replaceable.** DungeonMindBuddy is the first real production consumer, not the definition of the library.
10. **Performance optimizations may not change meaning.** Cache/reuse boundaries must preserve source/provenance freshness and exact revision identity.

## 4. Current public capability boundary

### Read capabilities

The current client contract proven during DungeonMindBuddy R.3 is:

- head or exact-revision projection;
- campaign, world-owned, and cross-campaign scope;
- GM and PLAYER admissibility;
- exact object lookup;
- deterministic graph-only search/referent resolution;
- bounded depth-1/depth-2 neighborhood expansion;
- evidence retrieval by object/relationship/assertion identity;
- source-anchor derivation and context-bound revalidation;
- explicit missing, truncation, coverage, and fail-closed errors.

The transport-neutral application services are the authority for these semantics. Product adapters may reshape DTOs or perform bounded presentation joins, but may not reconstruct a foreign graph or recover excluded rows.

### Write capabilities

DungeonMind owns:

- contributions and identity/governance records;
- finalized contribution review;
- exact-parent materialization;
- atomic publication and head CAS;
- idempotent publication recovery;
- existing-world adoption and the single governed V4 source-classification repair already accepted for Eldyrwild.

The write model remains independent from any particular product review UI.

## 5. Persistence and authority

PostgreSQL is the durable implementation for the living Eldyrwild authority, behind repository ports.

The graph authority is not "whatever row is latest". Public graph identity is the immutable published revision plus the explicit world head.

Source identity is durable, but source bodies may live elsewhere. DungeonMind stores and validates the identities/digests needed to prove evidence and anchor validity. Product-local opening of source bytes is not graph authority.

Derived semantic/vector indexes are rebuildable and subordinate to graph/source authority.

## 6. Semantic profile boundary

DungeonMind owns:

- semantic-profile refs and descriptor contracts;
- digest-pinned profile identity;
- registry ports;
- qualified-term admission.

`dungeonmind_dnd` owns D&D-specific profile descriptors, vocabularies, and pure candidate/planning adapters.

The generic kernel must not import the D&D package. A deployment chooses which descriptors to load through configuration.

Extensibility is empirical: a future second profile should be used as a probe of this boundary. We do not add a generic cross-profile interpretation layer before a concrete consumer demonstrates the need.

## 7. Read architecture and R.3a

The landed R.1/R.2 native read path currently performs:

```text
head lookup
→ revision load
→ parse immutable graph payload
→ scope projection
   → source artifact/revision provenance validation
→ retrieval-specific work
```

R.2a and the real R.3 consumer witness showed that repeated full projection dominates native-read latency.

R.3a is permitted to introduce a reusable **WorldGraph read context** whose purpose is to avoid repeated work while preserving one coherent read.

Expected safe decomposition:

```text
exact immutable graph revision
  → parsed revision reuse

current coherent source/provenance view
  + selected revision
  + scope/admissibility
  → scoped read context
  → retrieval operations
```

### Cache-safety rule

A parsed immutable graph revision may be reused by exact revision identity.

An authorized/scoped projection may **not** be reused across requests solely by `(revision, scope, campaign, admissibility)`, because source visibility, campaign ownership, lifecycle, and source-revision validity may change without publishing a new graph revision.

Any broader reuse must carry an exact coherent source/provenance state identity or equivalent invalidation proof. Prefer the smallest design supported by measurement.

## 8. Ownership map

| Concern | Owner |
| --- | --- |
| World Graph identity, immutable revisions, head CAS | DungeonMind |
| Source/evidence identity and provenance admission | DungeonMind |
| Scope, admissibility, projection, graph retrieval | DungeonMind |
| Semantic-profile identity/admission | DungeonMind |
| D&D semantic meaning | `dungeonmind_dnd` profile package |
| Contribution review and graph publication | DungeonMind |
| In-memory/PostgreSQL adapters | DungeonMind |
| Production DB lifecycle/backups/network/secrets | deployment owner |
| Product UI and work context | client product |
| Product-local source opening/presentation joins | client product |
| Agent harness/model/tool loop/context budgeting | client product — DungeonMindBuddy for the current system |
| Product agent roles and tool availability | client product/harness |
| Retrieval benchmark methodology external to this repo | benchmark owner; DungeonMind consumes evidence, not authority |

## 9. Dependency rules

```text
contracts
   ▲
domain
   ▲
application
   ▲
infrastructure / optional service adapters
```

Core must not require UI frameworks, agent frameworks, model providers, database drivers, or sibling product repositories at import time.

No runtime import from DungeonMindBuddy is allowed.

The profile dependency is one-way: the generic kernel does not import `dungeonmind_dnd`.

## 10. Architecture fitness rule

Post-cutover, architecture is evaluated by evidence rather than by preservation of founding abstractions.

For each meaningful subsystem, record:

- named current consumer;
- why the responsibility belongs in DungeonMind;
- runtime and conceptual cost;
- correctness failure it prevents;
- concrete extension it has enabled.

Classify it as:

- **ESSENTIAL COMPLEXITY**;
- **PRODUCTIVE ABSTRACTION**;
- **UNPROVEN ABSTRACTION**;
- **ACCIDENTAL COMPLEXITY**;
- **HISTORICAL RESIDUE**.

A successful optimization pass may cache, collapse, move, freeze, or delete. "It might be useful someday" is not sufficient retention evidence.

The living evidence ledger starts in [REPORT-2026-08-23-independent-library-transition.md](../Reports/REPORT-2026-08-23-independent-library-transition.md).
